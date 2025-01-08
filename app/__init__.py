import os

from flask import Flask
from notifications_utils import logging, request_helper
from notifications_utils.base64_uuid import base64_to_uuid, uuid_to_base64
from werkzeug.routing import BaseConverter, ValidationError

from app.config import configs
from app.monkeytype_config import MonkeytypeConfig
from app.utils.antivirus import AntivirusClient
from app.utils.store import DocumentStore, ScanFilesDocumentStore

document_store = DocumentStore()  # noqa: I001
scan_files_document_store = ScanFilesDocumentStore()  # noqa: I001
antivirus_client = AntivirusClient()  # noqa: I001

from .download.views import download_blueprint  # noqa: I001
from .upload.views import upload_blueprint  # noqa: I001
from .healthcheck import healthcheck_blueprint  # noqa: I001
from .xray_test import xray_blueprint  # noqa: I001


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
    config = configs[os.environ["NOTIFY_ENVIRONMENT"]]

    application.url_map.converters["base64_uuid"] = Base64UUIDConverter

    request_helper.init_app(application)
    logging.init_app(application)

    application.logger.info(f"Notify config: {config.get_safe_config()}")

    document_store.init_app(application)
    scan_files_document_store.init_app(application)
    antivirus_client.init_app(application)

    application.register_blueprint(download_blueprint)
    application.register_blueprint(upload_blueprint)
    application.register_blueprint(healthcheck_blueprint)
    application.register_blueprint(xray_blueprint)

    # Specify packages to be traced by MonkeyType. This can be overriden
    # via the MONKEYTYPE_TRACE_MODULES environment variable. e.g:
    # MONKEYTYPE_TRACE_MODULES="app.,notifications_utils."
    if os.environ["NOTIFY_ENVIRONMENT"] == "development":
        packages_prefix = ["app.", "notifications_utils."]
        application.monkeytype_config = MonkeytypeConfig(packages_prefix)

    return application
