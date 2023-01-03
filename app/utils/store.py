import os
import uuid

import boto3
from botocore.exceptions import ClientError as BotoClientError

from app.utils.scan_files import ScanVerdicts

class DocumentStoreError(Exception):
    pass

class SuspiciousContentError(Exception):
    pass

class MaliciousContentError(Exception):
    pass

class ScanInProgressError(Exception):
    pass

BAD_SCAN_VERDICTS = [ScanVerdicts.SUSPICIOUS.value, ScanVerdicts.MALICIOUS.value]

class DocumentStore:
    def __init__(self, bucket=None):
        self.s3 = boto3.client("s3")
        self.bucket = bucket

    def init_app(self, app):
        self.bucket = app.config['DOCUMENTS_BUCKET']

    def put(self, service_id, document_stream, sending_method, mimetype='application/pdf'):
        """
        returns dict {'id': 'some-uuid', 'encryption_key': b'32 byte encryption key'}
        """

        encryption_key = self.generate_encryption_key()
        document_id = str(uuid.uuid4())

        self.s3.put_object(
            Bucket=self.bucket,
            Key=self.get_document_key(service_id, document_id, sending_method),
            Body=document_stream,
            ContentType=mimetype,
            SSECustomerKey=encryption_key,
            SSECustomerAlgorithm='AES256'
        )

        return {
            'id': document_id,
            'encryption_key': encryption_key
        }

    def get(self, service_id, document_id, decryption_key, sending_method):
        """
        decryption_key should be raw bytes
        """
        try:
            document = self.s3.get_object(
                Bucket=self.bucket,
                Key=self.get_document_key(service_id, document_id, sending_method),
                SSECustomerKey=decryption_key,
                SSECustomerAlgorithm='AES256'
            )

        except BotoClientError as e:
            raise DocumentStoreError(e.response['Error'])
        
        try:
            response = self.s3.get_object_tagging(
                Bucket=self.bucket,
                Key=self.get_document_key(service_id, document_id, sending_method)
            )
            tag_dict = {t["Key"]: t["Value"] for t in response["TagSet"]}
            av_status = tag_dict["av-status"]
            if av_status == ScanVerdicts.IN_PROGRESS.value:
                raise ScanInProgressError("Content scanning is in progress")

            if av_status == ScanVerdicts.SUSPICIOUS.value:
                raise SuspiciousContentError("Suspicious content detected")
            
            if av_status == ScanVerdicts.MALICIOUS.value:
                raise MaliciousContentError("Malicious content detected")

        except BotoClientError as e:
            raise DocumentStoreError(e.response['Error'])

        return {
            'body': document['Body'],
            'mimetype': document['ContentType'],
            'size': document['ContentLength']
        }

    def generate_encryption_key(self):
        return os.urandom(32)

    def get_document_key(self, service_id, document_id, sending_method=None):
        key_prefix = 'tmp/' if sending_method == 'attach' else ''
        return f"{key_prefix}{service_id}/{document_id}"
