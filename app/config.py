import os
from typing import Any

from dotenv import load_dotenv
from environs import Env
from flask_env import MetaFlaskEnv

env = Env()
env.read_env()
load_dotenv()


class Config(metaclass=MetaFlaskEnv):
    DEBUG = env.bool("DEBUG", False)

    SECRET_KEY = os.getenv("SECRET_KEY", "secret-key")
    AUTH_TOKENS = os.getenv("AUTH_TOKENS", "auth-token")

    DOCUMENTS_BUCKET = os.getenv("DOCUMENTS_BUCKET", "development-notification-canada-ca-document-download")
    SCAN_FILES_DOCUMENTS_BUCKET = os.getenv(
        "SCAN_FILES_DOCUMENTS_BUCKET", "development-notification-canada-ca-document-download-scan-files"
    )

    ALLOWED_MIME_TYPES = [
        "application/pdf",
        "application/CDFV2",
        "text/csv",
        "text/plain",
        "application/msword",  # .doc
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "image/jpeg",
        "image/png",
        "application/vnd.ms-excel",  # .xls
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
        "application/vnd.apple.numbers",  # "Numbers" app on macOS
    ]
    EXTRA_MIME_TYPES = os.getenv("EXTRA_MIME_TYPES", "")

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024 + 1024

    HTTP_SCHEME = os.getenv("HTTP_SCHEME", "http")
    BACKEND_HOSTNAME = os.getenv("BACKEND_HOSTNAME", "localhost:7000")

    NOTIFY_APP_NAME = os.getenv("NOTIFY_APP_NAME", "Name")
    NOTIFY_LOG_PATH = os.getenv("NOTIFY_LOG_PATH", "application.log")

    ANTIVIRUS_API_HOST = os.getenv("ANTIVIRUS_API_HOST", "http://localhost:6016")
    ANTIVIRUS_API_KEY = os.getenv("ANTIVIRUS_API_KEY", "")

    @classmethod
    def get_sensitive_config(cls) -> list[str]:
        "List of config keys that contain sensitive information"
        return [
            "SECRET_KEY",
            "AUTH_TOKENS",
            "ANTIVIRUS_API_KEY",
        ]

    @classmethod
    def get_config(cls, sensitive_config: list[str]) -> dict[str, Any]:
        "Returns a dict of config keys and values"
        config = {}
        for attr in dir(cls):
            attr_value = "***" if attr in sensitive_config else getattr(cls, attr)
            if not attr.startswith("__") and not callable(attr_value):
                config[attr] = attr_value
        return config

    @classmethod
    def get_safe_config(cls) -> dict[str, Any]:
        "Returns a dict of config keys and values with sensitive values masked"
        return cls.get_config(cls.get_sensitive_config())


class Test(Config):
    DEBUG = True

    # used during tests as a domain name
    SERVER_NAME = "document-download.test"

    SECRET_KEY = "test-secret"
    AUTH_TOKENS = "auth-token:test-token:test-token-2"

    DOCUMENTS_BUCKET = "test-bucket"

    ANTIVIRUS_API_HOST = "https://test-antivirus"
    ANTIVIRUS_API_KEY = "test-antivirus-secret"

    BACKEND_HOSTNAME = "localhost:7000"


class Development(Config):
    DEBUG = True


class Production(Config):
    DEBUG = False


class Staging(Production):
    pass


class Scratch(Production):
    pass


class Dev(Production):
    pass


configs = {
    "test": Test,
    "scratch": Scratch,
    "development": Development,
    "staging": Staging,
    "production": Production,
    "dev": Dev,
}
