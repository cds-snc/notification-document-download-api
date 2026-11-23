import io
import zipfile
from pathlib import Path

import pytest
from app.utils import mime
from app.utils.mime import get_mime_type

MIME_FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "mime"
LONG_PAYLOAD_SIZE = 2050
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Valid packages whose large, uncompressed first entry makes libmagic report application/zip.
DOCX_ZIP_HEADER_FIXTURE = MIME_FIXTURE_DIR / "docx_zip_header_sample.docx"
XLSX_ZIP_HEADER_FIXTURE = MIME_FIXTURE_DIR / "xlsx_zip_header_sample.xlsx"

REAL_MIME_SAMPLES = [
    ("application/x-ole-storage", "xls_sample.xls"),
    ("application/x-ole-storage", "doc_sample.doc"),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx_sample.docx"),
    ("image/jpeg", "jpg_sample.jpg"),
    ("application/pdf", "pdf_sample.pdf"),
    ("image/png", "png_sample.png"),
    (("text/plain", "text/csv"), "csv_sample.csv"),
    ("text/plain", "txt_sample.txt"),
    ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx_sample.xlsx"),
]


@pytest.mark.parametrize("expected_mimes, fixture_name", REAL_MIME_SAMPLES)
def test_short_mime_detection(expected_mimes, fixture_name):
    payload = (MIME_FIXTURE_DIR / fixture_name).read_bytes()[:2047]

    assert len(payload) < 2048
    expected_mimes = (expected_mimes,) if isinstance(expected_mimes, str) else expected_mimes
    assert get_mime_type(io.BytesIO(payload)) in expected_mimes


@pytest.mark.parametrize("expected_mimes, fixture_name", REAL_MIME_SAMPLES)
def test_long_mime_detection(expected_mimes, fixture_name):
    payload = (MIME_FIXTURE_DIR / fixture_name).read_bytes()
    payload += b" " * max(0, LONG_PAYLOAD_SIZE - len(payload))

    assert len(payload) > 2049
    expected_mimes = (expected_mimes,) if isinstance(expected_mimes, str) else expected_mimes
    assert get_mime_type(io.BytesIO(payload)) in expected_mimes


def rebuild_package(fixture, renames=None, replacements=None, transforms=None):
    """Copy a fixture package, keeping entry order and compression so libmagic still reports application/zip."""
    renames = renames or {}
    replacements = replacements or {}
    transforms = transforms or {}
    output = io.BytesIO()
    with zipfile.ZipFile(fixture) as source, zipfile.ZipFile(output, "w") as target:
        for info in source.infolist():
            data = source.read(info)
            for old, new in replacements.get(info.filename, []):
                data = data.replace(old, new)
            if info.filename in transforms:
                data = transforms[info.filename](data)
            target.writestr(renames.get(info.filename, info.filename), data, compress_type=info.compress_type)
    return output.getvalue()


@pytest.mark.parametrize(
    "fixture, filename, expected_mime",
    [
        (DOCX_ZIP_HEADER_FIXTURE, "resume.docx", DOCX_MIME),
        (DOCX_ZIP_HEADER_FIXTURE, "RESUME.DOCX", DOCX_MIME),
        (XLSX_ZIP_HEADER_FIXTURE, "budget.xlsx", XLSX_MIME),
        (XLSX_ZIP_HEADER_FIXTURE, "BUDGET.XLSX", XLSX_MIME),
    ],
)
def test_ooxml_with_zip_header_is_detected_from_package_contents(fixture, filename, expected_mime):
    payload = fixture.read_bytes()

    assert get_mime_type(io.BytesIO(payload)) == "application/zip"
    assert get_mime_type(io.BytesIO(payload), filename) == expected_mime


@pytest.mark.parametrize(
    "fixture, filename",
    [
        (DOCX_ZIP_HEADER_FIXTURE, "resume.xlsx"),
        (XLSX_ZIP_HEADER_FIXTURE, "budget.docx"),
        (DOCX_ZIP_HEADER_FIXTURE, "resume.zip"),
    ],
)
def test_ooxml_package_is_not_detected_when_extension_does_not_match(fixture, filename):
    assert get_mime_type(io.BytesIO(fixture.read_bytes()), filename) == "application/zip"


@pytest.mark.parametrize("filename", ["resume.docx", "budget.xlsx"])
def test_generic_zip_named_as_ooxml_is_not_detected_as_ooxml(filename):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("readme.txt", "not an OOXML package")

    assert get_mime_type(io.BytesIO(payload.getvalue()), filename) == "application/zip"


def test_docx_main_part_is_found_through_package_relationship():
    payload = rebuild_package(
        DOCX_ZIP_HEADER_FIXTURE,
        renames={"word/document.xml": "word/document2.xml", "word/_rels/document.xml.rels": "word/_rels/document2.xml.rels"},
        replacements={
            "_rels/.rels": [(b"word/document.xml", b"word/document2.xml")],
            "[Content_Types].xml": [(b"/word/document.xml", b"/word/document2.xml")],
        },
    )

    assert get_mime_type(io.BytesIO(payload), "resume.docx") == DOCX_MIME


def test_ooxml_part_names_are_matched_case_insensitively():
    payload = rebuild_package(
        XLSX_ZIP_HEADER_FIXTURE,
        replacements={"[Content_Types].xml": [(b'PartName="/xl/workbook.xml"', b'PartName="/XL/Workbook.xml"')]},
    )

    assert get_mime_type(io.BytesIO(payload), "budget.xlsx") == XLSX_MIME


@pytest.mark.parametrize(
    "replacements",
    [
        # Macro-enabled documents have a different main content type.
        {"[Content_Types].xml": [(b"wordprocessingml.document.main+xml", b"ms-word.document.macroEnabled.main+xml")]},
        # The officeDocument relationship points to a part that isn't in the package.
        {"_rels/.rels": [(b'Target="word/document.xml"', b'Target="word/missing.xml"')]},
    ],
)
def test_invalid_docx_package_is_not_detected_as_docx(replacements):
    payload = rebuild_package(DOCX_ZIP_HEADER_FIXTURE, replacements=replacements)

    assert get_mime_type(io.BytesIO(payload), "resume.docx") == "application/zip"


def test_corrupt_central_directory_offset_is_not_detected_as_ooxml():
    payload = bytearray(DOCX_ZIP_HEADER_FIXTURE.read_bytes())
    end_of_central_directory = payload.rfind(b"PK\x05\x06")
    # Point the central directory past the archive start so zipfile computes a negative seek.
    payload[end_of_central_directory + 16 : end_of_central_directory + 20] = (0xFFFFFFF0).to_bytes(4, "little")

    assert get_mime_type(io.BytesIO(bytes(payload)), "resume.docx") == "application/zip"


def to_utf16(data):
    return data.decode("utf-8").replace('encoding="UTF-8"', 'encoding="UTF-16"').encode("utf-16")


BILLION_LAUGHS_DTD = (
    b'<!DOCTYPE Types [<!ENTITY a "aaaaaaaaaa">'
    + b"".join(b'<!ENTITY %s "%s">' % (chr(98 + i).encode(), (b"&%s;" % chr(97 + i).encode()) * 10) for i in range(9))
    + b"]>"
)


@pytest.mark.parametrize(
    "replacements, transforms",
    [
        ({"[Content_Types].xml": [(b"?>", b"?>" + BILLION_LAUGHS_DTD), (b"</Types>", b"&j;</Types>")]}, {}),
        ({"[Content_Types].xml": [(b"?>", b"?><!DOCTYPE Types>")]}, {}),
        ({"_rels/.rels": [(b"?>", b"?><!DOCTYPE Relationships>")]}, {}),
        # A UTF-16 DOCTYPE isn't visible to a byte search for "<!DOCTYPE".
        ({"[Content_Types].xml": [(b"?>", b"?><!DOCTYPE Types>")]}, {"[Content_Types].xml": to_utf16}),
    ],
)
def test_package_xml_with_dtd_is_rejected_before_entity_expansion(mocker, replacements, transforms):
    fromstring = mocker.spy(mime.ET, "fromstring")
    payload = rebuild_package(DOCX_ZIP_HEADER_FIXTURE, replacements=replacements, transforms=transforms)

    assert get_mime_type(io.BytesIO(payload), "resume.docx") == "application/zip"
    for call in fromstring.call_args_list:
        assert b"DOCTYPE" not in call.args[0]
        assert "DOCTYPE".encode("utf-16-le") not in call.args[0]


def test_utf16_package_xml_without_dtd_is_accepted():
    payload = rebuild_package(DOCX_ZIP_HEADER_FIXTURE, transforms={"[Content_Types].xml": to_utf16})

    assert get_mime_type(io.BytesIO(payload), "resume.docx") == DOCX_MIME
