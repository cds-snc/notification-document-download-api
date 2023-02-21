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
    ScanInProgressError,
    SuspiciousContentError,
)

download_blueprint = Blueprint("download", __name__, url_prefix="")

MALICIOUS_CONTENT_ERROR_CODE = 423
SCAN_IN_PROGRESS_ERROR_CODE = 428
SCAN_TIMEOUT_SECONDS = 10 * 60


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
        check_scan_verdict(service_id, document_id)
    except (MaliciousContentError, SuspiciousContentError) as e:
        current_app.logger.info(
            "Malicious content detected, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), MALICIOUS_CONTENT_ERROR_CODE
    except ScanInProgressError as e:
        age_seconds = scan_files_document_store.get_object_age_seconds(
            service_id, document_id, sending_method
        )
        if age_seconds > SCAN_TIMEOUT_SECONDS:
            current_app.logger.info(
                "Scan timed out for document: {}".format(e),
                extra={
                    "service_id": service_id,
                    "document_id": document_id,
                },
            )
            return jsonify(scan_verdict="scan_timed_out"), 200

        current_app.logger.info(
            "Scan in progress, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), SCAN_IN_PROGRESS_ERROR_CODE
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
        check_scan_verdict(service_id, document_id)
    except (MaliciousContentError, SuspiciousContentError) as e:
        current_app.logger.info(
            "Malicious content detected, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), MALICIOUS_CONTENT_ERROR_CODE
    except ScanInProgressError as e:
        age_seconds = scan_files_document_store.get_object_age_seconds(
            service_id, document_id, sending_method
        )
        if age_seconds > SCAN_TIMEOUT_SECONDS:
            current_app.logger.info(
                "Scan timed out for document: {}".format(e),
                extra={
                    "service_id": service_id,
                    "document_id": document_id,
                },
            )
            return jsonify(scan_verdict="scan_timed_out"), 200

        current_app.logger.info(
            "Scan in progress, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), SCAN_IN_PROGRESS_ERROR_CODE
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


@download_blueprint.route(
    "/services/<uuid:service_id>/documents/<uuid:document_id>/scan-verdict", methods=["POST"]
)
def check_scan_verdict(service_id, document_id):
    sending_method = request.form.get("sending_method")
    try:
        av_status = scan_files_document_store.check_scan_verdict(service_id, document_id, sending_method)
    except (MaliciousContentError, SuspiciousContentError) as e:
        current_app.logger.info(
            "Malicious content detected, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), MALICIOUS_CONTENT_ERROR_CODE
    except ScanInProgressError as e:
        age_seconds = scan_files_document_store.get_object_age_seconds(
            service_id, document_id, sending_method
        )
        if age_seconds > SCAN_TIMEOUT_SECONDS:
            current_app.logger.info(
                "Scan timed out for document: {}".format(e),
                extra={
                    "service_id": service_id,
                    "document_id": document_id,
                },
            )
            return jsonify(scan_verdict="scan_timed_out"), 200

        current_app.logger.info(
            "Scan in progress, refused to download document: {}".format(e),
            extra={
                "service_id": service_id,
                "document_id": document_id,
            },
        )
        return jsonify(error=str(e)), SCAN_IN_PROGRESS_ERROR_CODE
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
