import os

from flask import Flask
from notifications_utils import logging, request_helper

from app.config import configs
from app.utils.store import DocumentStore
from app.utils.antivirus import AntivirusClient

document_store = DocumentStore() # noqa, has to be imported before views
antivirus_client = AntivirusClient() # noqa

from .download.views import download_blueprint
from .upload.views import upload_blueprint
from .healthcheck import healthcheck_blueprint


def create_app():
    application = Flask('app', static_folder=None)
    application.config.from_object(configs[os.environ['NOTIFY_ENVIRONMENT']])

    request_helper.init_app(application)
    logging.init_app(application)

    document_store.init_app(application)
    antivirus_client.init_app(application)

    application.register_blueprint(download_blueprint)
    application.register_blueprint(upload_blueprint)
    application.register_blueprint(healthcheck_blueprint)

    return application
