import os
from flask_env import MetaFlaskEnv
from dotenv import load_dotenv
from notifications_utils import logging

load_dotenv()


class Config(metaclass=MetaFlaskEnv):
    DEBUG = os.getenv("DEBUG", False)

    SECRET_KEY = os.getenv("SECRET_KEY", "secret-key")
    AUTH_TOKENS = os.getenv("AUTH_TOKENS", "auth-token")

    DOCUMENTS_BUCKET = os.getenv("DOCUMENTS_BUCKET", "development-notification-canada-ca-document-download")

    ALLOWED_MIME_TYPES = [
        'application/pdf',
        'text/csv',
        'text/plain',
        'application/msword',  # .doc
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
        'image/jpeg',
        'image/png',
        'application/vnd.ms-excel',  # .xls
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
        'application/vnd.apple.numbers',  # "Numbers" app on macOS
    ]
    EXTRA_MIME_TYPES = os.getenv("EXTRA_MIME_TYPES", "")

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024 + 1024

    HTTP_SCHEME = os.getenv("HTTP_SCHEME", "http")
    FRONTEND_HOSTNAME = os.getenv("FRONTEND_HOSTNAME", "localhost:7001")

    NOTIFY_APP_NAME = os.getenv("NOTIFY_APP_NAME", "Name")
    NOTIFY_LOG_PATH = os.getenv("NOTIFY_LOG_PATH", "application.log")

    ANTIVIRUS_API_HOST = os.getenv("ANTIVIRUS_API_HOST", "http://localhost:6016")
    ANTIVIRUS_API_KEY = os.getenv("ANTIVIRUS_API_KEY", "")

    MLWR_HOST = os.getenv("MLWR_HOST", False)
    MLWR_USER = os.getenv("MLWR_USER", "")
    MLWR_KEY = os.getenv("MLWR_KEY", "")

    @classmethod
    def get_sensitive_config(cls) -> list[str]:
        "List of config keys that contain sensitive information"
        return [
            "ANTIVIRUS_API_KEY",
            "AUTH_TOKENS",
            "MLWR_KEY",
            "MLWR_USER",
            "SECRET_KEY",
        ]

    @classmethod
    def get_safe_config(cls) -> dict:
        "Returns a dict of config keys and values with sensitive values masked"
        return logging.get_class_attrs(cls, cls.get_sensitive_config())


class Test(Config):
    DEBUG = True

    # used during tests as a domain name
    SERVER_NAME = 'document-download.test'

    SECRET_KEY = 'test-secret'
    AUTH_TOKENS = 'auth-token:test-token:test-token-2'

    DOCUMENTS_BUCKET = 'test-bucket'

    ANTIVIRUS_API_HOST = 'https://test-antivirus'
    ANTIVIRUS_API_KEY = 'test-antivirus-secret'

    FRONTEND_HOSTNAME = 'localhost:7001'
    MLWR_HOST = "localhost"


class Development(Config):
    DEBUG = True


class Production(Config):
    DEBUG = False


class Staging(Production):
    pass


configs = {
    'test': Test,
    'development': Development,
    'staging': Staging,
    'production': Production,
}
