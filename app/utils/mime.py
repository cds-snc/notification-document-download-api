import pathlib
import posixpath
import xml.etree.ElementTree as ET
import zipfile
import zlib
from xml.parsers import expat

import magic

# Maps a filename extension to (MIME type to report, required content type of the package's main part).
OOXML_TYPES = {
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    ),
    ".xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    ),
}

CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
RELATIONSHIPS_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_DOCUMENT_RELATIONSHIP_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
}
MAX_PACKAGE_XML_SIZE = 64 * 1024


def get_mime_type(document_stream, filename=None):
    try:
        mime_type = magic.from_buffer(document_stream.read(2048), mime=True)
        ooxml_type = OOXML_TYPES.get(pathlib.Path(filename or "").suffix.lower())
        # libmagic only inspects the leading ZIP entries, so OOXML files with a large first entry look like plain ZIPs.
        if mime_type == "application/zip" and ooxml_type:
            document_stream.seek(0)
            if get_ooxml_main_content_type(document_stream) == ooxml_type[1]:
                mime_type = ooxml_type[0]
    finally:
        document_stream.seek(0)

    return mime_type


def parse_package_xml(data):
    # OPC forbids DTDs; rejecting them up front prevents entity-expansion attacks.
    def reject_dtd(*args):
        raise ValueError("DTDs are not allowed in OOXML package XML")

    checker = expat.ParserCreate()
    checker.StartDoctypeDeclHandler = reject_dtd
    checker.Parse(data, True)
    return ET.fromstring(data)


def get_ooxml_main_content_type(document_stream):
    """Return the content type of the main part of an OOXML package, or None if it isn't a valid package."""
    try:
        with zipfile.ZipFile(document_stream) as package:
            # OPC part names are case-insensitive.
            members = {info.filename.lower(): info for info in package.infolist()}

            def read_xml(part_name):
                info = members.get(part_name.lower())
                if info is None or info.file_size > MAX_PACKAGE_XML_SIZE:
                    return None
                return parse_package_xml(package.read(info))

            relationships = read_xml("_rels/.rels")
            content_types = read_xml("[Content_Types].xml")
            if relationships is None or content_types is None:
                return None

            main_part = next(
                (
                    posixpath.normpath(posixpath.join("/", rel.attrib.get("Target", ""))).lower()
                    for rel in relationships.iter(f"{{{RELATIONSHIPS_NAMESPACE}}}Relationship")
                    if rel.attrib.get("Type") in OFFICE_DOCUMENT_RELATIONSHIP_TYPES
                    and rel.attrib.get("TargetMode", "Internal") == "Internal"
                ),
                None,
            )
            if main_part is None or main_part.lstrip("/") not in members:
                return None
    except (
        ET.ParseError,
        expat.ExpatError,
        KeyError,
        OSError,
        RuntimeError,
        EOFError,
        NotImplementedError,
        ValueError,
        zlib.error,
        zipfile.BadZipFile,
    ):
        return None

    for override in content_types.iter(f"{{{CONTENT_TYPES_NAMESPACE}}}Override"):
        if override.attrib.get("PartName", "").lower() == main_part:
            return override.attrib.get("ContentType")

    extension = posixpath.splitext(main_part)[1].lstrip(".")
    for default in content_types.iter(f"{{{CONTENT_TYPES_NAMESPACE}}}Default"):
        if default.attrib.get("Extension", "").lower() == extension:
            return default.attrib.get("ContentType")

    return None
