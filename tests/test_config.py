import importlib
import os

import pytest
from app import config


@pytest.fixture
def reload_config():
    """
    Reset config, by simply re-running config.py from a fresh environment
    """
    old_env = os.environ.copy()
    yield
    os.environ = old_env
    importlib.reload(config)


def test_get_config(reload_config):
    config.Config.DOCUMENTS_BUCKET = "test-documents-bucket"
    config.Config.SCAN_FILES_DOCUMENTS_BUCKET = "test-scan-files-bucket"
    logged_config = config.Config.get_config([])
    assert logged_config["DOCUMENTS_BUCKET"] == "test-documents-bucket"
    assert logged_config["SCAN_FILES_DOCUMENTS_BUCKET"] == "test-scan-files-bucket"

    config.Config.SECRET_KEY = "1234"
    logged_config = config.Config.get_config(["SECRET_KEY"])
    assert logged_config["SECRET_KEY"] == "***"

    for key, _ in logged_config.items():
        assert not key.startswith("__")
        assert not callable(getattr(config.Config, key))


def test_get_safe_config(mocker, reload_config):
    mock_get_config = mocker.patch("app.config.Config.get_config")
    mock_get_sensitive_config = mocker.patch("app.config.Config.get_sensitive_config")

    config.Config.get_safe_config()
    assert mock_get_config.called
    assert mock_get_sensitive_config.called


def get_sensitive_config():
    sensitive_config = config.Config.get_sensitive_config()
    assert sensitive_config
    for key in sensitive_config:
        assert key
