import uuid
from unittest import mock

import pytest
from app.utils.store import (
    DocumentStore,
    DocumentStoreError,
    MaliciousContentError,
    ScanFailedError,
    ScanFilesDocumentStore,
    ScanInProgressError,
    ScanUnsupportedError,
)
from botocore.exceptions import ClientError as BotoClientError
from freezegun import freeze_time

from tests.conftest import Matcher, set_config


@pytest.fixture
def store(mocker):
    mock_boto = mocker.patch("app.utils.store.boto3")
    mock_boto.client.return_value.get_object.return_value = {
        "Body": mock.Mock(),
        "ContentType": "application/pdf",
        "ContentLength": 100,
    }
    store = DocumentStore(bucket="test-bucket")
    return store


@pytest.fixture
def scan_files_store(mocker):
    mock_boto = mocker.patch("app.utils.store.boto3")
    mock_boto.client.return_value.get_object.return_value = {
        "Body": mock.Mock(),
        "ContentType": "application/pdf",
        "ContentLength": 100,
    }
    store = ScanFilesDocumentStore(bucket="test-bucket")
    return store


def test_document_store_init_app(app, store):
    with set_config(app, DOCUMENTS_BUCKET="test-bucket-2"):
        store.init_app(app)

    assert store.bucket == "test-bucket-2"


def test_get_document_key(store):
    assert store.get_document_key("service-id", "doc-id") == "service-id/doc-id"


def test_document_key_with_uuid(store):
    service_id = uuid.uuid4()
    document_id = uuid.uuid4()

    assert store.get_document_key(service_id, document_id) == "{}/{}".format(str(service_id), str(document_id))


def test_put_document(store):
    ret = store.put("service-id", mock.Mock(), sending_method="link")

    assert ret == {
        "id": Matcher("UUID length match", lambda x: len(x) == 36),
        "encryption_key": Matcher("32 bytes", lambda x: len(x) == 32 and isinstance(x, bytes)),
    }

    store.s3.put_object.assert_called_once_with(
        Body=mock.ANY,
        Bucket="test-bucket",
        ContentType="application/pdf",
        Key=Matcher("document key", lambda x: x.startswith("service-id/") and len(x) == 11 + 36),
        SSECustomerKey=ret["encryption_key"],
        SSECustomerAlgorithm="AES256",
    )


def test_put_document_attach_tmp_dir(store):
    ret = store.put("service-id", mock.Mock(), sending_method="attach")

    assert ret == {
        "id": Matcher("UUID length match", lambda x: len(x) == 36),
        "encryption_key": Matcher("32 bytes", lambda x: len(x) == 32 and isinstance(x, bytes)),
    }

    store.s3.put_object.assert_called_once_with(
        Body=mock.ANY,
        Bucket="test-bucket",
        ContentType="application/pdf",
        Key=Matcher(
            "document key",
            lambda x: x.startswith("tmp/service-id/") and len(x) == 15 + 36,
        ),
        SSECustomerKey=ret["encryption_key"],
        SSECustomerAlgorithm="AES256",
    )


def test_get_document(store):
    assert store.get("service-id", "document-id", bytes(32), sending_method="link") == {
        "body": mock.ANY,
        "mimetype": "application/pdf",
        "size": 100,
    }

    store.s3.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="service-id/document-id",
        SSECustomerAlgorithm="AES256",
        # 32 null bytes
        SSECustomerKey=bytes(32),
    )


def test_get_document_attach_tmp_dir(store):
    store.s3.get_object_tagging = mock.Mock(
        return_value={"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "NO_THREATS_FOUND"}]}
    )
    assert store.get("service-id", "document-id", bytes(32), sending_method="attach") == {
        "body": mock.ANY,
        "mimetype": "application/pdf",
        "size": 100,
    }

    store.s3.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="tmp/service-id/document-id",
        SSECustomerAlgorithm="AES256",
        # 32 null bytes
        SSECustomerKey=bytes(32),
    )


def test_get_document_with_boto_error(store):
    store.s3.get_object = mock.Mock(
        side_effect=BotoClientError({"Error": {"Code": "Error code", "Message": "Error message"}}, "GetObject")
    )

    with pytest.raises(DocumentStoreError):
        store.get("service-id", "document-id", "0f0f0f", sending_method="link")


def test_get_document_with_scan_in_progress(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(return_value={"TagSet": []})
    with pytest.raises(ScanInProgressError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_flagged_malicious_guardduty(scan_files_store):
    """Test GuardDuty THREATS_FOUND verdict raises MaliciousContentError"""
    scan_files_store.s3.get_object_tagging = mock.Mock(
        return_value={"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "THREATS_FOUND"}]}
    )
    with pytest.raises(MaliciousContentError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_clean_guardduty(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(
        return_value={"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "NO_THREATS_FOUND"}]}
    )
    result = scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")
    assert result == "NO_THREATS_FOUND"


def test_get_document_scan_unsupported_guardduty(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(
        return_value={"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "UNSUPPORTED"}]}
    )
    with pytest.raises(ScanUnsupportedError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_scan_failed_access_denied_guardduty(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(
        return_value={"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "ACCESS_DENIED"}]}
    )
    with pytest.raises(ScanFailedError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_scan_failed_failed_guardduty(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(
        return_value={"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "FAILED"}]}
    )
    with pytest.raises(ScanFailedError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_flagged_malicious_scanfiles(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(return_value={"TagSet": [{"Key": "av-status", "Value": "malicious"}]})
    with pytest.raises(MaliciousContentError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_flagged_suspicious_scanfiles(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(return_value={"TagSet": [{"Key": "av-status", "Value": "suspicious"}]})
    with pytest.raises(MaliciousContentError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_clean_scanfiles(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(return_value={"TagSet": [{"Key": "av-status", "Value": "clean"}]})
    result = scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")
    assert result == "clean"


def test_get_document_scan_failed_error_scanfiles(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(return_value={"TagSet": [{"Key": "av-status", "Value": "error"}]})
    with pytest.raises(ScanFailedError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_get_document_scan_failed_unable_to_scan_scanfiles(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(return_value={"TagSet": [{"Key": "av-status", "Value": "unable_to_scan"}]})
    with pytest.raises(ScanFailedError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


def test_guardduty_tag_takes_precedence_over_scanfiles_clean(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(
        return_value={
            "TagSet": [
                {"Key": "GuardDutyMalwareScanStatus", "Value": "NO_THREATS_FOUND"},
                {"Key": "av-status", "Value": "malicious"},
            ]
        }
    )
    # Should not raise an error since GuardDuty tag indicates clean
    result = scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")
    assert result == "NO_THREATS_FOUND"


def test_guardduty_tag_takes_precedence_over_scanfiles_malicious(scan_files_store):
    scan_files_store.s3.get_object_tagging = mock.Mock(
        return_value={
            "TagSet": [
                {"Key": "GuardDutyMalwareScanStatus", "Value": "THREATS_FOUND"},
                {"Key": "av-status", "Value": "clean"},
            ]
        }
    )
    # Should raise MaliciousContentError since GuardDuty tag takes precedence
    with pytest.raises(MaliciousContentError):
        scan_files_store.check_scan_verdict("service-id", "document-id", sending_method="link")


@pytest.mark.parametrize(
    "last_modified, expected_age_seconds",
    [
        ("Fri, 17 Feb 2023 16:00:00 GMT", 60),
        ("Fri, 17 Feb 2023 16:00:59 GMT", 1),
        ("Fri, 17 Feb 2023 16:01:01 GMT", 0),
    ],
)
@freeze_time("2023-02-17 16:01:00.000000")
def test_get_object_age_seconds(scan_files_store, last_modified, expected_age_seconds):
    scan_files_store.s3.get_object_attributes = mock.Mock(
        return_value={"ResponseMetadata": {"HTTPHeaders": {"last-modified": last_modified}}}
    )
    age_data = scan_files_store.get_object_age_seconds("service-id", "document-id", sending_method="link")
    age_seconds = age_data["age_seconds"]
    assert age_seconds == expected_age_seconds
