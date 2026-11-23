import pathlib
import unicodedata

from flask import Blueprint, current_app, jsonify, request

from app import document_store, scan_files_document_store
from app.utils.authentication import check_auth
from app.utils.mime import get_mime_type
from app.utils.urls import get_api_download_url, get_direct_file_url

upload_blueprint = Blueprint("upload", __name__, url_prefix="")
upload_blueprint.before_request(check_auth)

ZERO_WIDTH_CHARACTERS = str.maketrans("", "", "\u200b\u2060\ufeff")


def normalize_filename(filename):
    # macOS screenshot names contain U+202F, and copy-pasted names often carry zero-width characters.
    if not filename:
        return None
    filename = filename.translate(ZERO_WIDTH_CHARACTERS)
    return "".join(" " if unicodedata.category(char) == "Zs" else char for char in filename) or None


@upload_blueprint.route("/services/<uuid:service_id>/documents", methods=["POST"])
def upload_document(service_id):
    if "document" not in request.files:
        return jsonify(error="No document upload"), 400

    # The API filename controls response/download metadata; the multipart filename
    # is a validation fallback for clients that omit the API field.
    filename = normalize_filename(request.form.get("filename"))
    file_extension = None
    validation_filename = filename or normalize_filename(request.files["document"].filename)
    if validation_filename:
        filename_suffix = pathlib.Path(validation_filename.lower()).suffix
        # Reject non-printable names before using the filename for extension checks.
        if not validation_filename.isprintable():
            current_app.logger.warning(
                "Rejecting upload with unsafe filename: %s",
                validation_filename,
                extra={"service_id": str(service_id)},
            )
            return jsonify(error="Unsupported or unsafe filename"), 400
        if filename:
            file_extension = filename_suffix.lstrip(".")

    # Detect the content from the upload stream, then apply compatibility fixes
    # for formats that libmagic commonly classifies too generally.
    mimetype = get_mime_type(request.files["document"], validation_filename)
    # Our MIME type auto-detection resolves CSV content as text/plain,
    # so we fix that if possible before checking the MIME allowlist.
    if validation_filename and validation_filename.lower().endswith(".csv") and mimetype == "text/plain":
        mimetype = "text/csv"

    # Unknown MIME types and unapproved MIME/extension mismatches are rejected.
    if not mime_type_is_allowed(mimetype, service_id, filename_suffix if validation_filename else None, validation_filename):
        allowed_extensions = current_app.config["ALLOWED_MIME_TYPES"].get(mimetype)
        if allowed_extensions is not None and not validation_filename:
            current_app.logger.warning(
                "Rejecting upload without a supported filename extension for MIME type %s",
                mimetype,
                extra={"service_id": str(service_id)},
            )
            return (
                jsonify(
                    error=(
                        "A filename with a supported extension is required for MIME type '{}'. " "Expected extensions: {}"
                    ).format(mimetype, allowed_extensions)
                ),
                400,
            )
        if allowed_extensions is not None:
            current_app.logger.warning(
                "Rejecting upload with unsupported filename extension %s for MIME type %s, filename: %s",
                filename_suffix,
                mimetype,
                validation_filename,
                extra={"service_id": str(service_id)},
            )
            return (
                jsonify(
                    error=("Filename extension '{}' is not supported for MIME type '{}'. " "Expected extensions: {}").format(
                        filename_suffix, mimetype, allowed_extensions
                    )
                ),
                400,
            )
        current_app.logger.warning(
            "Rejecting upload with unsupported MIME type %s, filename: %s",
            mimetype,
            validation_filename,
            extra={"service_id": str(service_id)},
        )
        return (
            jsonify(
                error="Unsupported document type '{}'. Supported types are: {}".format(
                    mimetype, list(current_app.config["ALLOWED_MIME_TYPES"])
                )
            ),
            400,
        )
    file_content = request.files["document"].read()

    sending_method = request.form.get("sending_method")

    # Store the document and an unencrypted scan copy with the detected MIME type.
    document = document_store.put(service_id, file_content, sending_method=sending_method, mimetype=mimetype)
    scan_files_document_store.put(service_id, document["id"], file_content, sending_method=sending_method, mimetype=mimetype)

    return (
        jsonify(
            status="ok",
            document={
                "id": document["id"],
                "direct_file_url": get_direct_file_url(
                    service_id=service_id,
                    document_id=document["id"],
                    key=document.get("encryption_key", ""),
                    sending_method=sending_method,
                ),
                "url": get_api_download_url(
                    service_id=service_id,
                    document_id=document["id"],
                    key=document.get("encryption_key", ""),
                    filename=filename,
                ),
                "filename": filename,
                "sending_method": sending_method,
                "mime_type": mimetype,
                "file_size": len(file_content),
                "file_extension": file_extension,
            },
        ),
        201,
    )


def mime_type_is_allowed(mimetype, service_id, file_extension=None, filename=None):
    allowed_extensions = current_app.config["ALLOWED_MIME_TYPES"].get(mimetype)
    if allowed_extensions is not None and file_extension in allowed_extensions:
        return True

    compatibility_extensions = current_app.config["MIME_EXTENSION_COMPATIBILITY"].get(mimetype, [])
    if file_extension in compatibility_extensions:
        current_app.logger.warning(
            "Allowing known MIME type mismatch: %s with filename extension %s, filename: %s",
            mimetype,
            file_extension,
            filename,
            extra={"service_id": str(service_id)},
        )
        return True

    return any(
        entry_parts[:2] == [str(service_id), mimetype] and (len(entry_parts) == 2 or entry_parts[2] == file_extension)
        for entry in current_app.config["EXTRA_MIME_TYPES"].split(",")
        for entry_parts in [entry.split(":", 2)]
    )
