import pathlib

from flask import Blueprint, current_app, jsonify, request

from app import document_store, scan_files_document_store
from app.utils import get_mime_type
from app.utils.authentication import check_auth
from app.utils.urls import get_api_download_url, get_direct_file_url

upload_blueprint = Blueprint("upload", __name__, url_prefix="")
upload_blueprint.before_request(check_auth)


@upload_blueprint.route("/services/<uuid:service_id>/documents", methods=["POST"])
def upload_document(service_id):
    if "document" not in request.files:
        return jsonify(error="No document upload"), 400

    # The API filename controls response/download metadata; the multipart filename
    # is a validation fallback for clients that omit the API field.
    filename = request.form.get("filename")
    file_extension = None
    validation_filename = filename or request.files["document"].filename
    if validation_filename:
        filename_suffix = pathlib.Path(validation_filename.lower()).suffix
        # Reject path-like names before using the filename for extension checks.
        if not filename_is_safe(validation_filename):
            return jsonify(error="Unsupported or unsafe filename"), 400
        if filename:
            file_extension = filename_suffix.lstrip(".")

    # Detect the content from the upload stream, then apply compatibility fixes
    # for formats that libmagic commonly classifies too generally.
    mimetype = get_mime_type(request.files["document"])
    # Our MIME type auto-detection resolves CSV content as text/plain,
    # so we fix that if possible before checking the MIME allowlist.
    if validation_filename and validation_filename.lower().endswith(".csv") and mimetype == "text/plain":
        mimetype = "text/csv"

    # Unknown MIME types are rejected; known MIME/extension mismatches are logged
    # but accepted so unusual user-supplied filenames do not break uploads.
    if not mime_type_is_allowed(mimetype, service_id, filename_suffix if validation_filename else None):
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


def mime_type_is_allowed(mimetype, service_id, file_extension=None):
    allowed_extensions = current_app.config["ALLOWED_MIME_TYPES"].get(mimetype)
    if allowed_extensions is not None and file_extension:
        if file_extension not in allowed_extensions:
            current_app.logger.warning("MIME type %s does not match filename extension %s", mimetype, file_extension)
        return True

    return any(
        entry_parts[:2] == [str(service_id), mimetype] and (len(entry_parts) == 2 or entry_parts[2] == file_extension)
        for entry in current_app.config["EXTRA_MIME_TYPES"].split(",")
        for entry_parts in [entry.split(":", 2)]
    )


def filename_is_safe(filename):
    if "/" in filename or "\\" in filename or "\x00" in filename:
        return False
    return True
