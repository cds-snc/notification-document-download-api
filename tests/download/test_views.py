import io
from uuid import UUID
from unittest import mock

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


@pytest.mark.parametrize(
    "endpoint",
    ["download.download_document", "download.download_document_b64"],
)
def test_document_download(client, store, endpoint):
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
def test_document_download_with_filename(client, store, endpoint):
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


def test_document_download_document_store_error(client, store):
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
    "endpoint, response_code, error",
    [
        ["download.download_document", 400, ScanInProgressError()],
        ["download.download_document_b64", 428, ScanInProgressError()],
        ["download.download_document", 400, MaliciousContentError()],
        ["download.download_document_b64", 403, MaliciousContentError()],
        ["download.download_document", 400, SuspiciousContentError()],
        ["download.download_document_b64", 403, SuspiciousContentError()],
    ],
)
def test_content_scan_errors(client, store, endpoint, response_code, error):
    store.get.side_effect = error
    response = client.get(
        url_for(
            endpoint,
            service_id="00000000-0000-0000-0000-000000000000",
            document_id="ffffffff-ffff-ffff-ffff-ffffffffffff",
            key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
    )

    assert response.status_code == response_code
