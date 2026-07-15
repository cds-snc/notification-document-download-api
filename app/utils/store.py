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
        new_key = self.get_document_key(service_id, document_id, sending_method)

        try:
            # SSE-S3 for template_attach, SSE-C for all others
            if sending_method == "template_attach":
                document = self.s3.get_object(
                    Bucket=self.bucket,
                    Key=new_key,
                )
            else:
                document = self.s3.get_object(
                    Bucket=self.bucket,
                    Key=new_key,
                    SSECustomerKey=decryption_key,
                    SSECustomerAlgorithm="AES256",
                )

            return {
                "body": document["Body"],
                "mimetype": document["ContentType"],
                "size": document["ContentLength"],
            }
        except BotoClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey" and sending_method != "template_attach":
                # Fallback to old path structure for backward compatibility
                # Old structure: {service_id}/{document_id} for link, tmp/{service_id}/{document_id} for attach
                old_key = self._get_old_document_key(service_id, document_id, sending_method)

                try:
                    current_app.logger.info(f"File not found at new path {new_key}, trying old path {old_key}")
                    document = self.s3.get_object(
                        Bucket=self.bucket,
                        Key=old_key,
                        SSECustomerKey=decryption_key,
                        SSECustomerAlgorithm="AES256",
                    )
                    current_app.logger.info(f"Found file at old path {old_key}, will serve from legacy location")

                    return {
                        "body": document["Body"],
                        "mimetype": document["ContentType"],
                        "size": document["ContentLength"],
                    }
                except BotoClientError:
                    pass  # Fall through to raise original error

            raise DocumentStoreError(e.response["Error"])

    def _get_old_document_key(self, service_id, document_id, sending_method):
        """
        Get the old path structure before folder reorganization.
        Used for backward compatibility during migration.
        """
        if sending_method == "attach":
            return f"tmp/{service_id}/{document_id}"
        else:
            # link mode or None
            return f"{service_id}/{document_id}"

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
        self._get_old_document_key = staticmethod(self._get_old_document_key_impl)

    def init_app(self, app):
        self.bucket = app.config["SCAN_FILES_DOCUMENTS_BUCKET"]
        print(f"self.bucket: {self.bucket}")

    @staticmethod
    def _get_old_document_key_impl(service_id, document_id, sending_method):
        """
        Get the old path structure before folder reorganization.
        Used for backward compatibility during migration.
        """
        if sending_method == "attach":
            return f"tmp/{service_id}/{document_id}"
        else:
            # link mode or None
            return f"{service_id}/{document_id}"

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
        Falls back to old path structure for backward compatibility during migration.
        """

        new_key = self.get_document_key(service_id, document_id, sending_method)

        try:
            response = self.s3.get_object_tagging(Bucket=self.bucket, Key=new_key)
        except BotoClientError as e:
            # Fallback to old path for legacy files (only if NoSuchKey and not template_attach)
            if e.response["Error"]["Code"] == "NoSuchKey" and sending_method != "template_attach":
                old_key = self._get_old_document_key(service_id, document_id, sending_method)
                try:
                    current_app.logger.info(f"Scan verdict not found at new path {new_key}, trying old path {old_key}")
                    response = self.s3.get_object_tagging(Bucket=self.bucket, Key=old_key)
                    current_app.logger.info(f"Found object at old path {old_key} for scan verdict check")
                except BotoClientError:
                    # Object doesn't exist at either path
                    raise DocumentStoreError(e.response["Error"])
            else:
                raise DocumentStoreError(e.response["Error"])

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
        Falls back to old path structure for backward compatibility during migration.
        """

        new_key = self.get_document_key(service_id, document_id, sending_method)

        try:
            # ETag doesn't matter, but I need to specify ObjectAttributes
            response = self.s3.get_object_attributes(
                Bucket=self.bucket,
                Key=new_key,
                ObjectAttributes=["ETag"],
            )
        except BotoClientError as e:
            # Fallback to old path for legacy files
            if e.response["Error"]["Code"] == "NoSuchKey" and sending_method != "template_attach":
                old_key = self._get_old_document_key(service_id, document_id, sending_method)
                try:
                    current_app.logger.info(f"Object not found at new path {new_key}, checking old path {old_key}")
                    response = self.s3.get_object_attributes(
                        Bucket=self.bucket,
                        Key=old_key,
                        ObjectAttributes=["ETag"],
                    )
                except BotoClientError as fallback_error:
                    raise DocumentStoreError(fallback_error.response["Error"])
            else:
                raise DocumentStoreError(e.response["Error"])

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
