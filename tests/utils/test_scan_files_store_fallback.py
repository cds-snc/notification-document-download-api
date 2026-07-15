from unittest.mock import MagicMock, patch

import pytest
from app.utils.store import (
    DocumentStoreError,
    MaliciousContentError,
    ScanFilesDocumentStore,
)
from botocore.exceptions import ClientError


@pytest.fixture
def app():
    from flask import Flask

    app = Flask(__name__)
    app.config["SCAN_FILES_DOCUMENTS_BUCKET"] = "test-bucket"
    return app


@pytest.fixture
def store(app):
    store = ScanFilesDocumentStore()
    store.init_app(app)
    return store


class TestScanFilesDocumentStoreFallback:
    """Tests for fallback logic in ScanFilesDocumentStore methods during migration"""

    def test_check_scan_verdict_fallback_to_old_path(self, app, store):
        """Verify check_scan_verdict falls back to old path when file not found at new path"""
        service_id = "service-123"
        document_id = "doc-456"

        # Mock S3 client to raise NoSuchKey on new path, succeed on old path
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        not_found_error = ClientError(error_response, "GetObjectTagging")

        with app.app_context():
            store.s3.get_object_tagging = MagicMock(
                side_effect=[
                    not_found_error,  # First call (new path) fails
                    {  # Second call (old path) succeeds
                        "TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "NO_THREATS_FOUND"}]
                    },
                ]
            )

            # Should not raise, should return the verdict
            verdict = store.check_scan_verdict(service_id, document_id, "link")
            assert verdict == "NO_THREATS_FOUND"

            # Verify both new and old paths were checked
            assert store.s3.get_object_tagging.call_count == 2
            calls = store.s3.get_object_tagging.call_args_list
            assert calls[0][1]["Key"] == f"api_link/{service_id}/{document_id}"
            assert calls[1][1]["Key"] == f"{service_id}/{document_id}"

    def test_check_scan_verdict_fallback_attach_mode(self, app, store):
        """Verify check_scan_verdict falls back to old tmp path for attach mode"""
        service_id = "service-123"
        document_id = "doc-456"

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        not_found_error = ClientError(error_response, "GetObjectTagging")

        with app.app_context():
            store.s3.get_object_tagging = MagicMock(
                side_effect=[not_found_error, {"TagSet": [{"Key": "av-status", "Value": "clean"}]}]
            )

            verdict = store.check_scan_verdict(service_id, document_id, "attach")
            assert verdict == "clean"

            # Verify paths
            calls = store.s3.get_object_tagging.call_args_list
            assert calls[0][1]["Key"] == f"api_attachments/{service_id}/{document_id}"
            assert calls[1][1]["Key"] == f"tmp/{service_id}/{document_id}"

    def test_check_scan_verdict_no_fallback_template_attach(self, app, store):
        """Verify check_scan_verdict does not fallback for template_attach mode"""
        service_id = "service-123"
        document_id = "doc-456"

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        not_found_error = ClientError(error_response, "GetObjectTagging")

        with app.app_context():
            store.s3.get_object_tagging = MagicMock(side_effect=not_found_error)

            # Should raise, no fallback for template_attach
            with pytest.raises(DocumentStoreError):
                store.check_scan_verdict(service_id, document_id, "template_attach")

            # Only one call should be made (no fallback)
            assert store.s3.get_object_tagging.call_count == 1

    def test_check_scan_verdict_malicious_on_old_path(self, app, store):
        """Verify malicious verdict is properly detected from old path"""
        service_id = "service-123"
        document_id = "doc-456"

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        not_found_error = ClientError(error_response, "GetObjectTagging")

        with app.app_context():
            store.s3.get_object_tagging = MagicMock(
                side_effect=[not_found_error, {"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "THREATS_FOUND"}]}]
            )

            with pytest.raises(MaliciousContentError):
                store.check_scan_verdict(service_id, document_id, "link")

    def test_check_scan_verdict_fails_both_paths(self, app, store):
        """Verify error raised when file not found at either path"""
        service_id = "service-123"
        document_id = "doc-456"

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        not_found_error = ClientError(error_response, "GetObjectTagging")

        with app.app_context():
            store.s3.get_object_tagging = MagicMock(side_effect=not_found_error)

            with pytest.raises(DocumentStoreError):
                store.check_scan_verdict(service_id, document_id, "link")

            # Both paths should be attempted
            assert store.s3.get_object_tagging.call_count == 2

    def test_delete_no_fallback_needed(self, app, store):
        """Verify delete works without fallback (only used for template_attach)"""
        service_id = "service-123"
        document_id = "doc-456"

        with app.app_context():
            store.s3.delete_object = MagicMock(return_value={})

            # Should succeed without fallback logic
            store.delete(service_id, document_id, "template_attach")

            # Verify only new path was called (no fallback)
            assert store.s3.delete_object.call_count == 1
            call = store.s3.delete_object.call_args_list[0]
            assert call[1]["Key"] == f"template_attachments/{service_id}/{document_id}"

    def test_get_object_age_seconds_fallback_to_old_path(self, app, store):
        """Verify get_object_age_seconds falls back to old path when file not found"""
        service_id = "service-123"
        document_id = "doc-456"

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        not_found_error = ClientError(error_response, "GetObjectAttributes")

        with app.app_context():
            store.s3.get_object_attributes = MagicMock(
                side_effect=[
                    not_found_error,  # First call (new path) fails
                    {  # Second call (old path) succeeds
                        "ResponseMetadata": {"HTTPHeaders": {"last-modified": "Fri, 17 Feb 2023 16:00:00 GMT"}}
                    },
                ]
            )

            # Mock datetime to have consistent test results
            from datetime import datetime

            with patch("app.utils.store.datetime") as mock_datetime:
                mock_now = datetime(2023, 2, 17, 16, 1, 0)  # 1 minute later
                mock_datetime.now.return_value = mock_now
                mock_datetime.strptime.side_effect = datetime.strptime

                result = store.get_object_age_seconds(service_id, document_id, "link")

                assert result["age_seconds"] == 60

                # Verify both paths were attempted
                assert store.s3.get_object_attributes.call_count == 2
                calls = store.s3.get_object_attributes.call_args_list
                assert calls[0][1]["Key"] == f"api_link/{service_id}/{document_id}"
                assert calls[1][1]["Key"] == f"{service_id}/{document_id}"

    def test_fallback_logs_messages(self, app, store):
        """Verify fallback operations are properly logged"""
        service_id = "service-123"
        document_id = "doc-456"

        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        not_found_error = ClientError(error_response, "GetObjectTagging")

        with app.app_context():
            store.s3.get_object_tagging = MagicMock(
                side_effect=[not_found_error, {"TagSet": [{"Key": "GuardDutyMalwareScanStatus", "Value": "NO_THREATS_FOUND"}]}]
            )

            with patch("app.utils.store.current_app.logger") as mock_logger:
                store.check_scan_verdict(service_id, document_id, "link")

                # Verify logging calls
                calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("new path" in str(call) for call in calls)
                assert any("old path" in str(call) for call in calls)

    def test_fallback_respects_non_notsuchkey_errors(self, app, store):
        """Verify fallback doesn't trigger for errors other than NoSuchKey"""
        service_id = "service-123"
        document_id = "doc-456"

        # AccessDenied error should not trigger fallback
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        access_denied_error = ClientError(error_response, "GetObjectTagging")

        with app.app_context():
            store.s3.get_object_tagging = MagicMock(side_effect=access_denied_error)

            with pytest.raises(DocumentStoreError):
                store.check_scan_verdict(service_id, document_id, "link")

            # Only one call should be made (no fallback)
            assert store.s3.get_object_tagging.call_count == 1
