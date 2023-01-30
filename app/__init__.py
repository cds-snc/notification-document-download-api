from datetime import datetime, time
import os
import threading

from flask import Flask, current_app
from notifications_utils import logging, request_helper
from notifications_utils.base64_uuid import base64_to_uuid, uuid_to_base64
from werkzeug.routing import BaseConverter, ValidationError

from app.config import configs
from app.utils.store import DocumentStore
from app.utils.antivirus import AntivirusClient

document_store = DocumentStore()  # noqa, has to be imported before views
antivirus_client = AntivirusClient()  # noqa

from .download.views import download_blueprint  # noqa
from .upload.views import upload_blueprint  # noqa
from .healthcheck import healthcheck_blueprint  # noqa


class Base64UUIDConverter(BaseConverter):
    def to_python(self, value):
        try:
            return base64_to_uuid(value)
        except ValueError:
            raise ValidationError()

    def to_url(self, value):
        try:
            return uuid_to_base64(value)
        except Exception:
            raise ValidationError()


def create_app():
    application = Flask("app", static_folder=None)
    application.config.from_object(configs[os.environ["NOTIFY_ENVIRONMENT"]])

    application.url_map.converters["base64_uuid"] = Base64UUIDConverter

    request_helper.init_app(application)
    logging.init_app(application)

    document_store.init_app(application)
    antivirus_client.init_app(application)

    application.register_blueprint(download_blueprint)
    application.register_blueprint(upload_blueprint)
    application.register_blueprint(healthcheck_blueprint)

    @application.before_first_request
    def before_first_request():
        """Start a background thread that cleans up old tasks."""

        def clean_old_tasks():
            """
            This function cleans up old tasks from our in-memory data structure.
            """
            global tasks
            while True:
                # Only keep tasks that are running or that finished less than 5
                # minutes ago.
                five_min_ago = datetime.timestamp(datetime.utcnow()) - 5 * 60
                tasks = {
                    task_id: task
                    for task_id, task in tasks.items()
                    if "completion_timestamp" not in task or task["completion_timestamp"] > five_min_ago
                }
                time.sleep(60)

        thread = threading.Thread(target=clean_old_tasks)
        thread.start()

    return application
