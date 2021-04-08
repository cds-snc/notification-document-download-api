import io

import pytest

from app.utils.antivirus import AntivirusError
from tests.conftest import set_config


@pytest.fixture
def store(mocker):
    return mocker.patch('app.upload.views.document_store')


@pytest.fixture
def antivirus(mocker):
    return mocker.patch('app.upload.views.upload_to_mlwr')


@pytest.mark.parametrize(
    "request_includes_filename, filename, in_frontend_url, expected_filename, sending_method", [
        (True, 'custom_filename.pdf', True, 'custom_filename.pdf', 'attach'),
        (False, 'whatever', False, None, 'link'),
    ]
)
def test_document_upload_returns_link_to_frontend(
    client,
    store,
    antivirus,
    request_includes_filename,
    filename,
    in_frontend_url,
    expected_filename,
    sending_method,
):
    store.put.return_value = {
        'id': 'ffffffff-ffff-ffff-ffff-ffffffffffff',
        'encryption_key': bytes(32),
    }
    antivirus.return_value = "abcd"
    data = {
        'document': (io.BytesIO(b'%PDF-1.4 file contents'), 'file.pdf'),
        'sending_method': sending_method
    }

    frontend_url_parts = [
        'http://localhost:7001',
        '/d/AAAAAAAAAAAAAAAAAAAAAA',
        '/_____________________w',
        '?key=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    ]

    expected_extension = None
    if request_includes_filename:
        data['filename'] = filename
        expected_extension = filename.split('.')[-1]

    if in_frontend_url:
        frontend_url_parts.append(f'&filename={filename}')

    response = client.post(
        '/services/00000000-0000-0000-0000-000000000000/documents',
        content_type='multipart/form-data',
        data=data
    )

    assert response.status_code == 201
    assert response.json == {
        'document': {
            'id': 'ffffffff-ffff-ffff-ffff-ffffffffffff',
            'url': ''.join(frontend_url_parts),
            'direct_file_url': ''.join([
                'http://document-download.test',
                '/services/00000000-0000-0000-0000-000000000000',
                '/documents/ffffffff-ffff-ffff-ffff-ffffffffffff',
                '?key=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
                f'&sending_method={sending_method}'
            ]),
            'mlwr_sid': 'abcd',
            'filename': expected_filename,
            'sending_method': sending_method,
            'mime_type': 'application/pdf',
            'file_size': 22,
            'file_extension': expected_extension
        },
        'status': 'ok'
    }


@pytest.mark.parametrize(
    "content, filename, expected_extension, expected_mime, expected_size", [
        (b'%PDF-1.4 file contents', 'file.pdf', 'pdf', 'application/pdf', 22),
        (b'Canada', 'text.txt', 'txt', 'text/plain', 6),
        (b'Canada', 'noextension', None, 'text/plain', 6),
        (b'foo,bar', 'file.csv', 'csv', 'text/csv', 7),
    ]
)
def test_document_upload_returns_size_and_mime(
    client,
    store,
    antivirus,
    content,
    filename,
    expected_extension,
    expected_mime,
    expected_size
):
    store.put.return_value = {
        'id': 'ffffffff-ffff-ffff-ffff-ffffffffffff',
        'encryption_key': bytes(32),
    }
    antivirus.return_value = "abcd"

    response = client.post(
        '/services/00000000-0000-0000-0000-000000000000/documents',
        content_type='multipart/form-data',
        data={
            'document': (io.BytesIO(content), filename),
            'sending_method': 'link',
            'filename': filename,
        }
    )

    assert response.status_code == 201
    assert response.json['document']['mime_type'] == expected_mime
    assert response.json['document']['file_size'] == expected_size
    assert response.json['document']['file_extension'] == expected_extension


@pytest.mark.skip(reason="NO AV")
def test_document_upload_virus_found(client, store, antivirus):
    antivirus.scan.return_value = False

    response = client.post(
        '/services/12345678-1111-1111-1111-123456789012/documents',
        content_type='multipart/form-data',
        data={
            'document': (io.BytesIO(b'%PDF-1.4 file contents'), 'file.pdf')
        }
    )

    assert response.status_code == 400
    assert response.json == {
        'error': "Document didn't pass the virus scan"
    }


@pytest.mark.skip(reason="NO AV")
def test_document_upload_virus_scan_error(client, store, antivirus):
    antivirus.scan.side_effect = AntivirusError(503, 'connection error')

    response = client.post(
        '/services/12345678-1111-1111-1111-123456789012/documents',
        content_type='multipart/form-data',
        data={
            'document': (io.BytesIO(b'%PDF-1.4 file contents'), 'file.pdf')
        }
    )

    assert response.status_code == 503
    assert response.json == {
        'error': "Antivirus API error"
    }


def test_document_upload_unknown_type(client):
    response = client.post(
        '/services/12345678-1111-1111-1111-123456789012/documents',
        content_type='multipart/form-data',
        data={
            'document': (io.BytesIO(b'\x00pdf file contents\n'), 'file.pdf')
        }
    )

    assert response.status_code == 400
    assert response.json == {
        'error': "Unsupported document type 'application/octet-stream'. Supported types are: ['application/pdf', 'text/csv', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'image/jpeg', 'image/png', 'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.apple.numbers']" # noqa
    }


@pytest.mark.parametrize("extra_mime_types,expected_status_code", [
    ("12345678-1111-1111-1111-123456789012:application/octet-stream", 201),
    ("12345678-1111-1111-1111-123456789012:application/octet-stream,foo:application/json", 201),
    ("foo:application/json,12345678-1111-1111-1111-123456789012:application/octet-stream", 201),
    ("12345678-1111-1111-1111-123456789012:application/json", 400),
    ("", 400),
])
def test_document_upload_extra_mime_type(
    app, client, mocker, store, antivirus, extra_mime_types,
    expected_status_code
):
    # Even if uploading "a PDF", make sure it's detected as "application/octet-stream"
    mocker.patch('app.upload.views.get_mime_type', return_value="application/octet-stream")

    store.put.return_value = {
        'id': 'ffffffff-ffff-ffff-ffff-ffffffffffff',
        'encryption_key': bytes(32),
    }
    antivirus.return_value = "abcd"

    with set_config(app, EXTRA_MIME_TYPES=extra_mime_types):
        response = client.post(
            '/services/12345678-1111-1111-1111-123456789012/documents',
            content_type='multipart/form-data',
            data={
                'document': (io.BytesIO(b'%PDF-1.5 ' + b'a' * (10 * 1024 * 1024 - 8)), 'file.pdf')
            }
        )
        assert response.status_code == expected_status_code


def test_document_file_size_just_right(client, store, antivirus):
    store.put.return_value = {
        'id': 'ffffffff-ffff-ffff-ffff-ffffffffffff',
        'encryption_key': bytes(32),
    }

    antivirus.return_value = "abcd"

    response = client.post(
        '/services/12345678-1111-1111-1111-123456789012/documents',
        content_type='multipart/form-data',
        data={
            'document': (io.BytesIO(b'%PDF-1.5 ' + b'a' * (10 * 1024 * 1024 - 8)), 'file.pdf')
        }
    )

    assert response.status_code == 201


def test_document_file_size_too_large(client):
    response = client.post(
        '/services/12345678-1111-1111-1111-123456789012/documents',
        content_type='multipart/form-data',
        data={
            'document': (io.BytesIO(b'%PDF-1.5 ' + b'a' * 11 * 1024 * 1024), 'file.pdf')
        }
    )

    assert response.status_code == 413
    assert response.json == {
        'error': "Uploaded document exceeds file size limit"
    }


def test_document_upload_no_document(client):
    response = client.post(
        '/services/12345678-1111-1111-1111-123456789012/documents',
        content_type='multipart/form-data',
        data={
            'file': (io.BytesIO(b'%PDF-1.4 file contents'), 'file.pdf')
        }
    )

    assert response.status_code == 400


def test_unauthorized_document_upload(client):
    response = client.post(
        '/services/12345678-1111-1111-1111-123456789012/documents',
        content_type='multipart/form-data',
        data={
            'document': (io.BytesIO(b'%PDF-1.4 file contents'), 'file.pdf')
        },
        headers={
            'Authorization': None,
        }
    )

    assert response.status_code == 401
