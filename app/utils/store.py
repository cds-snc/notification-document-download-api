import os
import uuid
from datetime import datetime

import boto3
from botocore.exceptions import ClientError as BotoClientError
from flask import current_app

from app.utils.guardduty import GUARDDUTY_SCAN_TAG, GuardDutyMalwareS3Verdicts
from app.utils.scan_files import SCAN_FILES_SCAN_TAG, ScanVerdicts


class DocumentStoreError(Exception):
    pass


class MaliciousContentError(Exception):
    pass


class ScanFailedError(Exception):
    pass


class ScanInProgressError(Exception):
    pass


class ScanUnsupportedError(Exception):
    pass


def get_document_key(service_id, document_id, sending_method=None):
    if sending_method == "attach":
        key_prefix = "api_attachments/"
    elif sending_method == "template_attach":
        key_prefix = "template_attachments/"
    else:
        key_prefix = "api_link/"
    return f"{key_prefix}{service_id}/{document_id}"


class DocumentStore:
    def __init__(self, bucket=None):
        self.s3 = boto3.client("s3")
        self.bucket = bucket
        self.get_document_key = get_document_key

    def init_app(self, app):
        self.bucket = app.config["DOCUMENTS_BUCKET"]

    def put(self, service_id, document_stream, sending_method, mimetype="application/pdf"):
        """
        returns dict {'id': 'some-uuid', 'encryption_key': b'32 byte encryption key'}
        For template_attach, uses SSE-S3 and encryption_key is None.
        """

        document_id = str(uuid.uuid4())

        # Use SSE-S3 for template_attach, SSE-C for all others
        if sending_method == "template_attach":
            self.s3.put_object(
                Bucket=self.bucket,
                Key=self.get_document_key(service_id, document_id, sending_method),
                Body=document_stream,
                ContentType=mimetype,
                ServerSideEncryption="AES256",
            )
            encryption_key = None
        else:
            encryption_key = self.generate_encryption_key()
            self.s3.put_object(
                Bucket=self.bucket,
                Key=self.get_document_key(service_id, document_id, sending_method),
                Body=document_stream,
                ContentType=mimetype,
                SSECustomerKey=encryption_key,
                SSECustomerAlgorithm="AES256",
            )

        return {"id": document_id, "encryption_key": encryption_key}

    def get(self, service_id, document_id, decryption_key, sending_method):
        """
        decryption_key should be raw bytes (not needed for template_attach)
        """
        try:
            # SSE-S3 for template_attach, SSE-C for all others
            if sending_method == "template_attach":
                document = self.s3.get_object(
                    Bucket=self.bucket,
                    Key=self.get_document_key(service_id, document_id, sending_method),
                )
            else:
                document = self.s3.get_object(
                    Bucket=self.bucket,
                    Key=self.get_document_key(service_id, document_id, sending_method),
                    SSECustomerKey=decryption_key,
                    SSECustomerAlgorithm="AES256",
                )

        except BotoClientError as e:
            raise DocumentStoreError(e.response["Error"])

        return {
            "body": document["Body"],
            "mimetype": document["ContentType"],
            "size": document["ContentLength"],
        }

    def delete(self, service_id, document_id, decryption_key, sending_method):
        """
        Delete a document from S3.
        decryption_key should be raw bytes (not needed for template_attach).
        """
        try:
            current_app.logger.info(f"Deleting document: {document_id} from service {service_id}")
            # SSE-S3 for template_attach, SSE-C for all others
            if sending_method == "template_attach":
                self.s3.delete_object(
                    Bucket=self.bucket,
                    Key=self.get_document_key(service_id, document_id, sending_method),
                )
            else:
                self.s3.delete_object(
                    Bucket=self.bucket,
                    Key=self.get_document_key(service_id, document_id, sending_method),
                    SSECustomerKey=decryption_key,
                    SSECustomerAlgorithm="AES256",
                )
        except BotoClientError as e:
            current_app.logger.error("Failed to delete document: {}".format(e))
            raise DocumentStoreError(e.response["Error"])

    def generate_encryption_key(self):
        return os.urandom(32)


class ScanFilesDocumentStore:
    def __init__(self, bucket=None):
        self.s3 = boto3.client("s3")
        self.bucket = bucket
        self.get_document_key = get_document_key

    def init_app(self, app):
        self.bucket = app.config["SCAN_FILES_DOCUMENTS_BUCKET"]
        print(f"self.bucket: {self.bucket}")

    def put(self, service_id, document_id, document_stream, sending_method, mimetype="application/pdf"):
        self.s3.put_object(
            Bucket=self.bucket,
            Key=self.get_document_key(service_id, document_id, sending_method),
            Body=document_stream,
            ContentType=mimetype,
        )

    def check_scan_verdict(self, service_id, document_id, sending_method):
        """
        S3 scanning will write the scan verdict as a tag on the S3 object.
        Inspect this value and raise an error accordingly.
        """

        try:
            response = self.s3.get_object_tagging(
                Bucket=self.bucket, Key=self.get_document_key(service_id, document_id, sending_method)
            )
            tag_dict = {t["Key"]: t["Value"] for t in response["TagSet"]}

            # Support both GuardDuty and ScanFiles tags for scan verdicts during the transition to GuardDuty
            av_status = tag_dict.get(GUARDDUTY_SCAN_TAG) or tag_dict.get(SCAN_FILES_SCAN_TAG)
            if av_status is None or av_status == ScanVerdicts.IN_PROGRESS.value:
                raise ScanInProgressError("Content scanning is in progress")
            elif av_status in (
                GuardDutyMalwareS3Verdicts.THREATS_FOUND,
                ScanVerdicts.MALICIOUS.value,
                ScanVerdicts.SUSPICIOUS.value,
            ):
                raise MaliciousContentError("Malicious content detected")
            elif av_status == GuardDutyMalwareS3Verdicts.UNSUPPORTED:
                raise ScanUnsupportedError("Scan unsupported for document")
            elif av_status in (
                GuardDutyMalwareS3Verdicts.ACCESS_DENIED,
                GuardDutyMalwareS3Verdicts.FAILED,
                ScanVerdicts.ERROR.value,
                ScanVerdicts.UNABLE_TO_SCAN.value,
            ):
                raise ScanFailedError(f"Scan failed with status {av_status}")
        except BotoClientError as e:
            raise DocumentStoreError(e.response["Error"])
        return av_status

    def delete(self, service_id, document_id, sending_method):
        """
        Delete a document from S3.
        """
        try:
            self.s3.delete_object(
                Bucket=self.bucket,
                Key=self.get_document_key(service_id, document_id, sending_method),
            )
        except BotoClientError as e:
            raise DocumentStoreError(e.response["Error"])

    def get_object_age_seconds(self, service_id, document_id, sending_method) -> dict:
        """
        Returns the object age in seconds, as well as some data for debugging purposes.
        Returns {"age_seconds": 0, ... } if the age would be negative.
        """

        try:
            # ETag doesn't matter, but I need to specify ObjectAttributes
            response = self.s3.get_object_attributes(
                Bucket=self.bucket,
                Key=self.get_document_key(service_id, document_id, sending_method),
                ObjectAttributes=["ETag"],
            )
            last_modified = response["ResponseMetadata"]["HTTPHeaders"]["last-modified"]
            last_modified_parsed = datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
            now = datetime.now()
            # last_modified is rounded to the nearest second and could be in the future
            if last_modified_parsed > now:
                age_seconds = 0
            else:
                age = now - last_modified_parsed
                age_seconds = age.seconds

            return {
                "age_seconds": age_seconds,
                "last_modified": last_modified,
                "last_modified_parsed": last_modified_parsed,
                "now": now,
            }

        except BotoClientError as e:
            raise DocumentStoreError(e.response["Error"])
