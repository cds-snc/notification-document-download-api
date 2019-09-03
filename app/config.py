import os
from flask_env import MetaFlaskEnv
from dotenv import load_dotenv

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
    ]

    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 + 1024

    HTTP_SCHEME = os.getenv("HTTP_SCHEME", "http")
    FRONTEND_HOSTNAME = os.getenv("FRONTEND_HOSTNAME", "localhost:7001")

    NOTIFY_APP_NAME = os.getenv("NOTIFY_APP_NAME", "Name")
    NOTIFY_LOG_PATH = os.getenv("NOTIFY_LOG_PATH", "application.log")

    ANTIVIRUS_API_HOST = os.getenv("ANTIVIRUS_API_HOST", "http://localhost:6016")
    ANTIVIRUS_API_KEY = os.getenv("ANTIVIRUS_API_KEY", "")

    MLWR_HOST = os.getenv("MLWR_HOST", False)
    MLWR_USER = os.getenv("MLWR_USER", "")
    MLWR_KEY = os.getenv("MLWR_KEY", "")


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


configs = {
    'test': Test,
    'development': Development,
    'production': Production,
}
