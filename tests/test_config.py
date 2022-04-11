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


def test_get_safe_config(mocker, reload_config):
    mock_get_class_attrs = mocker.patch("notifications_utils.logging.get_class_attrs")
    mock_get_sensitive_config = mocker.patch("app.config.Config.get_sensitive_config")

    config.Config.get_safe_config()
    assert mock_get_class_attrs.called
    assert mock_get_sensitive_config.called


def test_get_sensitive_config():
    sensitive_config = config.Config.get_sensitive_config()
    assert sensitive_config
    for key in sensitive_config:
        assert key
