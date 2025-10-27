from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    request,
    send_file,
)
from notifications_utils.base64_uuid import base64_to_bytes

from app import document_store, scan_files_document_store
from app.utils.store import (
    DocumentStoreError,
    MaliciousContentError,
    ScanFailedError,
    ScanInProgressError,
    ScanUnsupportedError,
)

download_blueprint = Blueprint("download", __name__, url_prefix="")

MALICIOUS_CONTENT_ERROR_CODE = 423
SCAN_IN_PROGRESS_ERROR_CODE = 428
SCAN_TIMEOUT_ERROR_CODE = 408
SCAN_TIMEOUT_SECONDS = 11 * 60
SCAN_FAILED_ERROR_CODE = 422


@download_blueprint.route("/services/<uuid:service_id>/documents/<uuid:document_id>", methods=["GET"])
def download_document(service_id, document_id):
    if "key" not in request.args:
        return jsonify(error="Missing decryption key"), 400

    filename = request.args.get("filename")
    sending_method = request.args.get("sending_method", "link")

    try:
        key = base64_to_bytes(request.args["key"])
    except ValueError:
        return jsonify(error="Invalid decryption key"), 400

    try:
        check_scan_verdict(service_id, document_id, sending_method)
    except MaliciousContentError as e:
        current_app.logger.info(
            "Malicious content detected, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), MALICIOUS_CONTENT_ERROR_CODE
    except ScanInProgressError as e:
        # return the document to the user in case the scan timed out
        current_app.logger.info("Scan is in progress but we will return the link, error is: {}".format(e))
        pass
    except ScanFailedError as e:
        # GuardDuty failed to scan the document. Log an error but allow download.
        current_app.logger.error("GuardDuty failed to scan document: {}".format(e))
        pass
    except ScanUnsupportedError as e:
        # GuardDuty was unable to scan the document. Log a warning but allow download.
        current_app.logger.warning("GuardDuty scan unsupported for document: {}".format(e))
        pass
    except DocumentStoreError as e:
        current_app.logger.info(
            "Failed to get tags from document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        abort(404)

    try:
        document = document_store.get(service_id, document_id, key, sending_method)
    except DocumentStoreError as e:
        current_app.logger.info(
            "Failed to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), 400

    response = make_response(
        send_file(
            document["body"],
            mimetype=document["mimetype"],
            # as_attachment can only be `True` if the filename is set
            as_attachment=(filename is not None),
            download_name=filename,
        )
    )
    response.headers["Content-Length"] = document["size"]
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return response


@download_blueprint.route("/d/<base64_uuid:service_id>/<base64_uuid:document_id>", methods=["GET"])
def download_document_b64(service_id, document_id):
    if "key" not in request.args:
        abort(404)

    filename = request.args.get("filename")
    sending_method = request.args.get("sending_method", "link")

    try:
        key = base64_to_bytes(request.args["key"])
    except ValueError:
        abort(404)

    try:
        check_scan_verdict(service_id, document_id, sending_method)
    except MaliciousContentError as e:
        current_app.logger.info(
            "Malicious content detected, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        abort(404)
    except ScanInProgressError as e:
        # at this point the email with the "link" type attachment has been sent
        # return the document to the user in case the scan timed out
        current_app.logger.info("Scan is in progress but we will return the link, error is: {}".format(e))
        pass
    except ScanFailedError as e:
        # GuardDuty failed to scan the document. Log an error but allow download.
        current_app.logger.error("GuardDuty failed to scan document: {}".format(e))
        pass
    except ScanUnsupportedError as e:
        # GuardDuty was unable to scan the document. Log a warning but allow download.
        current_app.logger.warning("GuardDuty scan unsupported for document: {}".format(e))
        pass
    except DocumentStoreError as e:
        current_app.logger.info(
            "Failed to get tags from document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        abort(404)

    try:
        document = document_store.get(service_id, document_id, key, sending_method)
    except DocumentStoreError as e:
        current_app.logger.info(
            "Failed to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        abort(404)

    response = make_response(
        send_file(
            document["body"],
            mimetype=document["mimetype"],
            # as_attachment can only be `True` if the filename is set
            as_attachment=(filename is not None),
            download_name=filename,
        )
    )
    response.headers["Content-Length"] = document["size"]
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    return response


@download_blueprint.route("/services/<uuid:service_id>/documents/<uuid:document_id>/scan-verdict", methods=["POST"])
def check_scan_verdict(service_id, document_id, sending_method=None):
    sending_method = request.form.get("sending_method", sending_method)
    try:
        av_status = scan_files_document_store.check_scan_verdict(service_id, document_id, sending_method)
    except MaliciousContentError as e:
        current_app.logger.info(
            "Malicious content detected, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), MALICIOUS_CONTENT_ERROR_CODE
    except ScanInProgressError as e:
        age_data = scan_files_document_store.get_object_age_seconds(service_id, document_id, sending_method)
        age_seconds = age_data["age_seconds"]
        current_app.logger.info(f"ScanInProgressError, age_data: {age_data}")
        if age_seconds > SCAN_TIMEOUT_SECONDS:
            current_app.logger.info(
                "Scan timed out for document: {}".format(e),
                extra={
                    "service_id": service_id,
                    "document_id": document_id,
                },
            )
            return jsonify(scan_verdict="scan_timed_out"), SCAN_TIMEOUT_ERROR_CODE

        current_app.logger.info(
            "Scan in progress, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), SCAN_IN_PROGRESS_ERROR_CODE
    except ScanUnsupportedError:
        current_app.logger.warning(
            "Scan unsupported for document",
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(scan_verdict="scan_unsupported"), SCAN_FAILED_ERROR_CODE
    except ScanFailedError as e:
        current_app.logger.error(
            "Scan failed for document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(scan_verdict="scan_failed"), SCAN_FAILED_ERROR_CODE
    except DocumentStoreError as e:
        current_app.logger.info(
            "Failed to get tags from document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        abort(404)
    return jsonify(scan_verdict=av_status), 200
