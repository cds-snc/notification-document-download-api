import io
from pathlib import Path

import pytest
from app.utils import get_mime_type

MIME_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "mime"
LONG_PAYLOAD_SIZE = 2050

REAL_MIME_SAMPLES = [
    (
        (
            "application/CDFV2",
            "application/vnd.ms-excel",
            "application/x-ole-storage",
        ),
        "xls_sample.xls",
    ),
    (("application/msword", "application/x-ole-storage"), "doc_sample.doc"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx_sample.docx"),
    ("image/jpeg", "jpg_sample.jpg"),
    ("application/pdf", "pdf_sample.pdf"),
    ("image/png", "png_sample.png"),
    (("text/csv", "text/plain"), "csv_sample.csv"),
    ("text/plain", "txt_sample.txt"),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx_sample.xlsx"),
]


@pytest.mark.parametrize("expected_mimes, fixture_name", REAL_MIME_SAMPLES)
def test_short_mime_detection(expected_mimes, fixture_name):
    payload = (MIME_FIXTURE_DIR / fixture_name).read_bytes()[:2047]

    assert len(payload) < 2048
    assert get_mime_type(io.BytesIO(payload)) in (expected_mimes if isinstance(expected_mimes, tuple) else (expected_mimes,))


@pytest.mark.parametrize("expected_mimes, fixture_name", REAL_MIME_SAMPLES)
def test_long_mime_detection(expected_mimes, fixture_name):
    payload = (MIME_FIXTURE_DIR / fixture_name).read_bytes()
    payload += b" " * max(0, LONG_PAYLOAD_SIZE - len(payload))

    assert len(payload) > 2049
    assert get_mime_type(io.BytesIO(payload)) in (expected_mimes if isinstance(expected_mimes, tuple) else (expected_mimes,))
