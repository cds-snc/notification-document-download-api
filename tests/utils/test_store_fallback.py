"""
Tests for S3 document store fallback logic during folder structure migration.
These tests verify that files not found at new paths are retrieved from old paths.
"""

from unittest import mock

import pytest
from app.utils.store import DocumentStore, DocumentStoreError
from botocore.exceptions import ClientError as BotoClientError


@pytest.fixture
def store_with_fallback(mocker):
    """Store fixture that simulates NoSuchKey errors for new paths"""
    mock_boto = mocker.patch("app.utils.store.boto3")

    store = DocumentStore(bucket="test-bucket")
    store.s3 = mock_boto.client.return_value

    return store


def test_fallback_api_link_mode_to_old_root_path(store_with_fallback, app):
    """Test fallback from new api_link/ path to old root path"""
    store = store_with_fallback

    # Mock: First call (new path) raises NoSuchKey, second call (old path) succeeds
    no_such_key_error = BotoClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")

    store.s3.get_object.side_effect = [
        no_such_key_error,
        {
            "Body": mock.Mock(),
            "ContentType": "application/pdf",
            "ContentLength": 100,
        },
    ]

    # Call get with api_link mode (default) within app context
    with app.app_context():
        result = store.get("service-id", "document-id", bytes(32), sending_method=None)

    # Verify result is successful
    assert result["mimetype"] == "application/pdf"
    assert result["size"] == 100

    # Verify we tried both paths
    assert store.s3.get_object.call_count == 2

    # Verify first call was to new path (api_link/)
    first_call = store.s3.get_object.call_args_list[0]
    assert "api_link/service-id/document-id" in str(first_call)

    # Verify second call was to old path (root)
    second_call = store.s3.get_object.call_args_list[1]
    assert "service-id/document-id" in str(second_call)


def test_fallback_attach_mode_to_old_tmp_path(store_with_fallback, app):
    """Test fallback from new api_attachments/ path to old tmp/ path"""
    store = store_with_fallback

    no_such_key_error = BotoClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")

    store.s3.get_object.side_effect = [
        no_such_key_error,
        {
            "Body": mock.Mock(),
            "ContentType": "application/pdf",
            "ContentLength": 100,
        },
    ]

    with app.app_context():
        result = store.get("service-id", "document-id", bytes(32), sending_method="attach")

    assert result["mimetype"] == "application/pdf"
    assert result["size"] == 100
    assert store.s3.get_object.call_count == 2

    # Verify first call was to new path (api_attachments/)
    first_call = store.s3.get_object.call_args_list[0]
    assert "api_attachments/service-id/document-id" in str(first_call)

    # Verify second call was to old path (tmp/)
    second_call = store.s3.get_object.call_args_list[1]
    assert "tmp/service-id/document-id" in str(second_call)


def test_no_fallback_for_template_attach_mode(store_with_fallback):
    """Test that template_attach mode does NOT use fallback logic"""
    store = store_with_fallback

    no_such_key_error = BotoClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")

    store.s3.get_object.side_effect = no_such_key_error

    # Should raise DocumentStoreError without attempting fallback
    with pytest.raises(DocumentStoreError):
        store.get("service-id", "document-id", None, sending_method="template_attach")

    # Should only be called once (no fallback attempt)
    assert store.s3.get_object.call_count == 1


def test_fallback_logs_messages(store_with_fallback, mocker, app):
    """Test that fallback logic logs appropriate messages"""
    store = store_with_fallback

    no_such_key_error = BotoClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")

    store.s3.get_object.side_effect = [
        no_such_key_error,
        {
            "Body": mock.Mock(),
            "ContentType": "application/pdf",
            "ContentLength": 100,
        },
    ]

    with app.app_context():
        mock_logger = mocker.patch("app.utils.store.current_app.logger")
        store.get("service-id", "document-id", bytes(32), sending_method="attach")

        # Verify logging was called
        assert mock_logger.info.call_count >= 2


def test_fallback_raises_error_if_both_paths_fail(store_with_fallback, app):
    """Test that error is raised if file not found at either path"""
    store = store_with_fallback

    no_such_key_error = BotoClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")

    # Both calls fail
    store.s3.get_object.side_effect = no_such_key_error

    with app.app_context():
        with pytest.raises(DocumentStoreError):
            store.get("service-id", "document-id", bytes(32), sending_method="attach")

    # Should have tried both paths
    assert store.s3.get_object.call_count == 2


def test_fallback_respects_other_error_types(store_with_fallback):
    """Test that non-NoSuchKey errors don't trigger fallback"""
    store = store_with_fallback

    access_denied_error = BotoClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "GetObject")

    store.s3.get_object.side_effect = access_denied_error

    with pytest.raises(DocumentStoreError):
        store.get("service-id", "document-id", bytes(32), sending_method="attach")

    # Should only try new path, not fallback
    assert store.s3.get_object.call_count == 1
