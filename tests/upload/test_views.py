import io

import pytest

from tests.conftest import set_config


@pytest.fixture
def store(mocker):
    return mocker.patch("app.upload.views.document_store")


@pytest.fixture
def scan_files_store(mocker):
    return mocker.patch("app.upload.views.scan_files_document_store")


@pytest.mark.parametrize(
    "request_includes_filename, filename, in_api_url, expected_filename, sending_method",
    [
        (True, "custom_filename.pdf", True, "custom_filename.pdf", "attach"),
        (False, "whatever", False, None, "link"),
    ],
)
def test_document_upload_returns_link_to_api(
    client,
    store,
    scan_files_store,
    request_includes_filename,
    filename,
    in_api_url,
    expected_filename,
    sending_method,
):
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    data = {
        "document": (io.BytesIO(b"%PDF-1.4 file contents"), "file.pdf"),
        "sending_method": sending_method,
    }

    api_url_parts = [
        "http://localhost:7000",
        "/d/AAAAAAAAAAAAAAAAAAAAAA",
        "/_____________________w",
        "?key=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    ]

    expected_extension = None
    if request_includes_filename:
        data["filename"] = filename
        expected_extension = filename.split(".")[-1]

    if in_api_url:
        api_url_parts.append(f"&filename={filename}")

    response = client.post(
        "/services/00000000-0000-0000-0000-000000000000/documents",
        content_type="multipart/form-data",
        data=data,
    )

    assert response.status_code == 201
    assert response.json == {
        "document": {
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "url": "".join(api_url_parts),
            "direct_file_url": "".join(
                [
                    "http://document-download.test",
                    "/services/00000000-0000-0000-0000-000000000000",
                    "/documents/ffffffff-ffff-ffff-ffff-ffffffffffff",
                    "?key=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                    f"&sending_method={sending_method}",
                ]
            ),
            "filename": expected_filename,
            "sending_method": sending_method,
            "mime_type": "application/pdf",
            "file_size": 22,
            "file_extension": expected_extension,
        },
        "status": "ok",
    }


@pytest.mark.parametrize(
    "content, filename, expected_extension, expected_mime, expected_size",
    [
        (b"%PDF-1.4 file contents", "file.pdf", "pdf", "application/pdf", 22),
        (
            b"%PDF-1.4 file contents",
            "Estimation de voyage - John Doe - Ste. Marie Canada - 2026-09-08.pdf",
            "pdf",
            "application/pdf",
            22,
        ),
        (b"Canada", "text.txt", "txt", "text/plain", 6),
        (b"foo,bar", "file.csv", "csv", "text/csv", 7),
        (b"foo,bar", "FILE.CSV", "csv", "text/csv", 7),
    ],
)
def test_document_upload_returns_size_and_mime(
    client,
    store,
    scan_files_store,
    content,
    filename,
    expected_extension,
    expected_mime,
    expected_size,
):
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    response = client.post(
        "/services/00000000-0000-0000-0000-000000000000/documents",
        content_type="multipart/form-data",
        data={
            "document": (io.BytesIO(content), filename or "fake"),
            "sending_method": "link",
            "filename": filename,
        },
    )

    assert response.status_code == 201
    assert response.json["document"]["mime_type"] == expected_mime
    assert response.json["document"]["file_size"] == expected_size
    assert response.json["document"]["file_extension"] == expected_extension


def test_document_upload_rejects_text_plain_without_filename(client):
    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"Canada"), "fake")},
    )

    assert response.status_code == 400


def test_document_upload_unknown_type(client):
    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"\x00pdf file contents\n"), "file.pdf")},
    )

    assert response.status_code == 400
    assert response.json == {
        "error": "Unsupported document type 'application/octet-stream'. Supported types are: ['application/pdf', 'application/CDFV2', 'text/csv', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'image/jpeg', 'image/png', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.apple.numbers']"  # noqa
    }


@pytest.mark.parametrize(
    "extra_mime_types,expected_status_code",
    [
        ("12345678-1111-1111-1111-123456789012:application/octet-stream:.pdf", 201),
        (
            "12345678-1111-1111-1111-123456789012:application/octet-stream:.pdf,foo:application/json:.json",
            201,
        ),
        (
            "foo:application/json:.json,12345678-1111-1111-1111-123456789012:application/octet-stream:.pdf",
            201,
        ),
        ("12345678-1111-1111-1111-123456789012:application/octet-stream:.custom", 400),
        ("12345678-1111-1111-1111-123456789012:application/json:.json", 400),
        ("", 400),
    ],
)
def test_document_upload_extra_mime_type(app, client, mocker, store, scan_files_store, extra_mime_types, expected_status_code):
    # Even if uploading "a PDF", make sure it's detected as "application/octet-stream"
    mocker.patch("app.upload.views.get_mime_type", return_value="application/octet-stream")

    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    with set_config(app, EXTRA_MIME_TYPES=extra_mime_types):
        response = client.post(
            "/services/12345678-1111-1111-1111-123456789012/documents",
            content_type="multipart/form-data",
            data={
                "document": (
                    io.BytesIO(b"%PDF-1.5 " + b"a" * (10 * 1024 * 1024 - 8)),
                    "file.pdf",
                )
            },
        )
        assert response.status_code == expected_status_code


def test_document_upload_extra_mime_type_rejects_unsupported_filename(app, client, mocker):
    mocker.patch("app.upload.views.get_mime_type", return_value="application/octet-stream")

    with set_config(
        app,
        EXTRA_MIME_TYPES="12345678-1111-1111-1111-123456789012:application/octet-stream:.pdf",
    ):
        response = client.post(
            "/services/12345678-1111-1111-1111-123456789012/documents",
            content_type="multipart/form-data",
            data={
                "document": (io.BytesIO(b"file contents"), "file.txt"),
                "filename": "file.txt",
            },
        )

    assert response.status_code == 400


def test_document_upload_extra_mime_type_without_extension_accepts_any_safe_extension(
    app, client, mocker, store, scan_files_store
):
    mocker.patch("app.upload.views.get_mime_type", return_value="application/octet-stream")
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    with set_config(
        app,
        EXTRA_MIME_TYPES="12345678-1111-1111-1111-123456789012:application/octet-stream",
    ):
        response = client.post(
            "/services/12345678-1111-1111-1111-123456789012/documents",
            content_type="multipart/form-data",
            data={
                "document": (io.BytesIO(b"custom file contents"), "file.custom"),
                "filename": "file.custom",
            },
        )

    assert response.status_code == 201
    assert response.json["document"]["mime_type"] == "application/octet-stream"


def test_document_upload_extra_mime_type_accepts_configured_extension(app, client, mocker, store, scan_files_store):
    mocker.patch("app.upload.views.get_mime_type", return_value="application/octet-stream")
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    with set_config(
        app,
        EXTRA_MIME_TYPES="12345678-1111-1111-1111-123456789012:application/octet-stream:.custom",
    ):
        response = client.post(
            "/services/12345678-1111-1111-1111-123456789012/documents",
            content_type="multipart/form-data",
            data={
                "document": (io.BytesIO(b"custom file contents"), "file.custom"),
                "filename": "file.custom",
            },
        )

    assert response.status_code == 201
    assert response.json["document"]["mime_type"] == "application/octet-stream"


def test_document_upload_extra_mime_type_rejects_unsupported_multipart_filename(app, client, mocker):
    mocker.patch("app.upload.views.get_mime_type", return_value="application/octet-stream")

    with set_config(
        app,
        EXTRA_MIME_TYPES="12345678-1111-1111-1111-123456789012:application/octet-stream:.pdf",
    ):
        response = client.post(
            "/services/12345678-1111-1111-1111-123456789012/documents",
            content_type="multipart/form-data",
            data={"document": (io.BytesIO(b"file contents"), "file.txt")},
        )

    assert response.status_code == 400


def test_document_upload_accepts_mismatched_builtin_mime_and_extension(client, mocker, store, scan_files_store):
    mocker.patch("app.upload.views.get_mime_type", return_value="application/pdf")
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"PDF contents"), "file.csv")},
    )

    assert response.status_code == 201


def test_document_upload_accepts_jpg_for_jpeg_mime(client, mocker, store, scan_files_store):
    mocker.patch("app.upload.views.get_mime_type", return_value="image/jpeg")
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"jpeg contents"), "file.jpg")},
    )

    assert response.status_code == 201


@pytest.mark.parametrize("mimetype", ["text/plain", "text/csv"])
def test_document_upload_accepts_log_for_text_mime(client, mocker, store, scan_files_store, mimetype):
    mocker.patch("app.upload.views.get_mime_type", return_value=mimetype)
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"log contents"), "file.log")},
    )

    assert response.status_code == 201


def test_document_file_size_just_right(client, store, scan_files_store):
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={
            "document": (
                io.BytesIO(b"%PDF-1.5 " + b"a" * (10 * 1024 * 1024 - 8)),
                "file.pdf",
            )
        },
    )

    assert response.status_code == 201


def test_document_file_size_too_large(client):
    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"%PDF-1.5 " + b"a" * 11 * 1024 * 1024), "file.pdf")},
    )

    assert response.status_code == 413
    assert response.json == {"error": "Uploaded document exceeds file size limit"}


def test_document_upload_no_document(client):
    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"file": (io.BytesIO(b"%PDF-1.4 file contents"), "file.pdf")},
    )

    assert response.status_code == 400


def test_unauthorized_document_upload(client):
    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"%PDF-1.4 file contents"), "file.pdf")},
        headers={
            "Authorization": None,
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "filename, expected_error",
    [
        ("../file.pdf", "Unsupported or unsafe filename"),
        ("C:\\file.pdf", "Unsupported or unsafe filename"),
    ],
)
def test_document_upload_rejects_unsupported_or_unsafe_filename(client, filename, expected_error):
    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={"document": (io.BytesIO(b"%PDF-1.4 file contents"), "file.pdf"), "filename": filename},
    )

    assert response.status_code == 400
    assert response.json["error"].startswith(expected_error)


def test_document_upload_accepts_allowlisted_filename(client, store, scan_files_store):
    store.put.return_value = {
        "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
        "encryption_key": bytes(32),
    }

    response = client.post(
        "/services/12345678-1111-1111-1111-123456789012/documents",
        content_type="multipart/form-data",
        data={
            "document": (io.BytesIO(b"%PDF-1.4 file contents"), "file.pdf"),
            "filename": "FILE.PDF",
        },
    )

    assert response.status_code == 201
    assert response.json["document"]["file_extension"] == "pdf"


@pytest.mark.parametrize(
    "content, filename",
    [
        (b"%PDF-1.4 file contents", "file.pdf"),
        (b"foo,bar", "file.csv"),
        (b"foo,bar", "FILE.CSV"),
    ],
)
def test_upload_document_adds_file_to_scan_files_bucket(
    client,
    store,
    scan_files_store,
    content,
    filename,
):
    doc_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    store.put.return_value = {
        "id": doc_id,
        "encryption_key": bytes(32),
    }

    response = client.post(
        "/services/00000000-0000-0000-0000-000000000000/documents",
        content_type="multipart/form-data",
        data={
            "document": (io.BytesIO(content), filename or "fake"),
            "sending_method": "link",
            "filename": filename,
        },
    )

    assert response.status_code == 201
    scan_files_store.put.assert_called_once()
