import io
from uuid import UUID
from unittest import mock
import json

from flask import url_for
import pytest

from app.utils.store import (
    DocumentStoreError,
    MaliciousContentError,
    ScanInProgressError,
    SuspiciousContentError,
)


@pytest.fixture
def store(mocker):
    return mocker.patch("app.download.views.document_store")


@pytest.fixture
def scan_files_store(mocker):
    return mocker.patch("app.download.views.scan_files_document_store")


@pytest.mark.parametrize(
    "endpoint",
    ["download.download_document", "download.download_document_b64"],
)
def test_document_download(client, store, endpoint, mocker):
    mocker.patch("app.download.views.check_scan_verdict", return_value=None)
    store.get.return_value = {
        "body": io.BytesIO(b"PDF document contents"),
        "mimetype": "application/pdf",
        "size": 100,
    }

    response = client.get(
        url_for(
            endpoint,
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 32 \x00 bytes
        )
    )

    assert response.status_code == 200
    assert response.get_data() == b"PDF document contents"
    assert dict(response.headers) == {
        "Cache-Control": mock.ANY,
        "Date": mock.ANY,
        "Content-Length": "100",
        "Content-Type": "application/pdf",
        "X-B3-SpanId": "None",
        "X-B3-TraceId": "None",
        "X-Robots-Tag": "noindex, nofollow",
    }
    store.get.assert_called_once_with(
        UUID("00000000-0000-0000-0000-000000000000"),
        UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        bytes(32),
        "link",
    )


@pytest.mark.parametrize(
    "endpoint",
    ["download.download_document", "download.download_document_b64"],
)
def test_document_download_with_filename(client, store, endpoint, mocker):
    mocker.patch("app.download.views.check_scan_verdict", return_value=None)
    store.get.return_value = {
        "body": io.BytesIO(b"PDF document contents"),
        "mimetype": "application/pdf",
        "size": 100,
    }

    response = client.get(
        url_for(
            "download.download_document",
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 32 \x00 bytes
            filename="custom_filename.pdf",
            sending_method="attach",
        )
    )

    assert response.status_code == 200
    assert response.get_data() == b"PDF document contents"
    assert dict(response.headers) == {
        "Cache-Control": mock.ANY,
        "Date": mock.ANY,
        "Content-Length": "100",
        "Content-Type": "application/pdf",
        "X-B3-SpanId": "None",
        "X-B3-TraceId": "None",
        "X-Robots-Tag": "noindex, nofollow",
        "Content-Disposition": "attachment; filename=custom_filename.pdf",
    }
    store.get.assert_called_once_with(
        UUID("00000000-0000-0000-0000-000000000000"),
        UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        bytes(32),
        "attach",
    )


def test_document_download_without_decryption_key(client, store):
    response = client.get(
        url_for(
            "download.download_document",
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        )
    )

    assert response.status_code == 400
    assert response.json == {"error": "Missing decryption key"}


def test_document_download_with_invalid_decryption_key(client):
    response = client.get(
        url_for(
            "download.download_document",
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            key="🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉🐦⁉?",
        )
    )

    assert response.status_code == 400
    assert response.json == {"error": "Invalid decryption key"}


def test_document_download_document_store_error(client, store, mocker):
    mocker.patch("app.download.views.check_scan_verdict", return_value=None)
    store.get.side_effect = DocumentStoreError("something went wrong")
    response = client.get(
        url_for(
            "download.download_document",
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
    )

    assert response.status_code == 400
    assert response.json == {"error": "something went wrong"}


@pytest.mark.parametrize(
    "endpoint, response_code, error, scan_return",
    [
        ["download.download_document", 200, ScanInProgressError(), 900],
        ["download.download_document", 428, ScanInProgressError(), 30],
        ["download.download_document", 423, MaliciousContentError(), 300],
        ["download.download_document", 423, SuspiciousContentError(), 300],
        ["download.download_document", 404, DocumentStoreError(), 300],
        ["download.download_document_b64", 200, ScanInProgressError(), 900],
        ["download.download_document_b64", 200, ScanInProgressError(), 30],
        ["download.download_document_b64", 404, MaliciousContentError(), 300],
        ["download.download_document_b64", 404, SuspiciousContentError(), 300],
        ["download.download_document_b64", 404, DocumentStoreError(), 300],
    ],
)
def test_document_download_check_scan_verdict_errors(
    client, store, scan_files_store, mocker, endpoint, response_code, error, scan_return
):
    mocker.patch("app.download.views.check_scan_verdict", side_effect=error)
    scan_files_store.get_object_age_seconds.return_value = scan_return
    store.get.return_value = store.get.return_value = {
        "body": io.BytesIO(b"PDF document contents"),
        "mimetype": "application/pdf",
        "size": 100,
    }
    response = client.get(
        url_for(
            endpoint,
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # 32 \x00 bytes
        )
    )
    assert response.status_code == response_code


@pytest.mark.parametrize(
    "response_code, error",
    [
        [428, ScanInProgressError()],
        [423, MaliciousContentError()],
        [423, SuspiciousContentError()],
        [404, DocumentStoreError()],
    ],
)
def test_content_scan_errors(client, scan_files_store, response_code, error):
    scan_files_store.check_scan_verdict.side_effect = error
    scan_files_store.get_object_age_seconds.return_value = 30
    response = client.post(
        url_for(
            "download.check_scan_verdict",
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        )
    )

    assert response.status_code == response_code


def test_content_scan_no_error(client, scan_files_store):
    scan_files_store.check_scan_verdict.return_value = "clean"
    response = client.post(
        url_for(
            "download.check_scan_verdict",
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        )
    )

    assert response.status_code == 200


def test_scan_times_out(client, scan_files_store):
    scan_files_store.check_scan_verdict.side_effect = ScanInProgressError()
    scan_files_store.get_object_age_seconds.return_value = 15 * 60
    response = client.post(
        url_for(
            "download.check_scan_verdict",
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
        )
    )
    assert response.status_code == 200
    assert json.loads(response.data) == {"scan_verdict": "scan_timed_out"}
