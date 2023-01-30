from datetime import datetime
from functools import wraps
import pathlib
import threading
import uuid

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException, InternalServerError

from app import document_store
from app.utils import get_mime_type
from app.utils.authentication import check_auth
from app.utils.urls import get_direct_file_url, get_api_download_url
from app.utils.scan_files import ScanVerdicts, get_scan_verdict

upload_blueprint = Blueprint("upload", __name__, url_prefix="")
upload_blueprint.before_request(check_auth)

tasks = {}


def async_api(wrapped_function):
    @wraps(wrapped_function)
    def new_function(*args, **kwargs):
        def task_call(flask_app, environ):
            # Create a request context similar to that of the original request
            # so that the task can have access to flask.g, flask.request, etc.
            with flask_app.request_context(environ):
                try:
                    tasks[task_id]["return_value"] = wrapped_function(*args, **kwargs)
                except HTTPException as e:
                    tasks[task_id]["return_value"] = current_app.handle_http_exception(e)
                except Exception as e:
                    # The function raised an exception, so we set a 500 error
                    tasks[task_id]["return_value"] = InternalServerError()
                    if current_app.debug:
                        # We want to find out if something happened so reraise
                        raise
                finally:
                    # We record the time of the response, to help in garbage
                    # collecting old tasks
                    tasks[task_id]["completion_timestamp"] = datetime.timestamp(datetime.utcnow())

                    # close the database session (if any)

        # Assign an id to the asynchronous task
        task_id = uuid.uuid4().hex

        # Record the task, and then launch it
        tasks[task_id] = {
            "task_thread": threading.Thread(
                target=task_call, args=(current_app._get_current_object(), request.environ)
            )
        }
        tasks[task_id]["task_thread"].start()

        print(f"task_id={task_id}")

    return new_function


@async_api
def scan_files_process(file_content, mimetype, service_id, document, sending_method):
    """
    This function will run in a new thread and will:
    - send the file to the scan-files API
    - recieve a verdict
    - update the av-status tag in on the corresponding object in S3
    """
    scan_verdict = get_scan_verdict(file_content, mimetype)
    # Add a `time.sleep(10)` here to test the async behaviour
    document_store.update_av_status(
        service_id=service_id,
        document_id=document["id"],
        sending_method=sending_method,
        scan_verdict=scan_verdict,
    )
    current_app.logger.info(f"scan verdict={scan_verdict} for document_id={document['id']}")


@upload_blueprint.route("/services/<uuid:service_id>/documents", methods=["POST"])
def upload_document(service_id):
    if "document" not in request.files:
        return jsonify(error="No document upload"), 400

    mimetype = get_mime_type(request.files["document"])
    if not mime_type_is_allowed(mimetype, service_id):
        return (
            jsonify(
                error="Unsupported document type '{}'. Supported types are: {}".format(
                    mimetype, current_app.config["ALLOWED_MIME_TYPES"]
                )
            ),
            400,
        )
    file_content = request.files["document"].read()

    filename = request.form.get("filename")
    file_extension = None
    if filename and "." in filename:
        file_extension = "".join(pathlib.Path(filename.lower()).suffixes).lstrip(".")

    # Our MIME type auto-detection resolves CSV content as text/plain,
    # so we fix that if possible
    if (filename or "").lower().endswith(".csv") and mimetype == "text/plain":
        mimetype = "text/csv"

    sending_method = request.form.get("sending_method")

    document = document_store.put(
        service_id,
        file_content,
        sending_method=sending_method,
        mimetype=mimetype,
        scan_verdict=ScanVerdicts.IN_PROGRESS,
    )

    if current_app.config["ANTIVIRUS_API_HOST"]:
        # will run in a new thread
        scan_files_process(file_content, mimetype, service_id, document, sending_method)

    return (
        jsonify(
            status="ok",
            document={
                "id": document["id"],
                "direct_file_url": get_direct_file_url(
                    service_id=service_id,
                    document_id=document["id"],
                    key=document["encryption_key"],
                    sending_method=sending_method,
                ),
                "url": get_api_download_url(
                    service_id=service_id,
                    document_id=document["id"],
                    key=document["encryption_key"],
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


def mime_type_is_allowed(mimetype, service_id):
    if mimetype in current_app.config["ALLOWED_MIME_TYPES"]:
        return True

    # Payload is formatted like "service_id1:mime1,service_id2:mime2"
    # Example:
    # "fccd5d86-afd6-491b-afa8-2ff592e1404f:application/octet-stream,95365643-8126-46f1-a222-e0c51fa918f2:application/json"
    return f"{service_id}:{mimetype}" in current_app.config["EXTRA_MIME_TYPES"]
