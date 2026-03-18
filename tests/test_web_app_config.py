import sys
import os
from pathlib import Path
import pytest
from unittest.mock import patch
from flask import Flask
from app.web.app import _configure_app


def test_cli_arg_takes_priority(monkeypatch, tmp_path):
    """--config argument wins over env var and platform default."""
    monkeypatch.setenv('DQ_CONFIG_PATH', str(tmp_path / 'env.yml'))
    from app.web.app import _resolve_config_path
    result = _resolve_config_path(str(tmp_path / 'cli.yml'))
    assert result == Path(tmp_path / 'cli.yml')


def test_env_var_used_when_no_cli_arg(monkeypatch, tmp_path):
    """DQ_CONFIG_PATH env var is used when --config is not provided."""
    monkeypatch.setenv('DQ_CONFIG_PATH', str(tmp_path / 'env.yml'))
    from app.web.app import _resolve_config_path
    result = _resolve_config_path(None)
    assert result == Path(tmp_path / 'env.yml')


def test_platform_default_windows(monkeypatch):
    """On Windows, default is ~/Documents/DQ Workbench/config.yml."""
    monkeypatch.delenv('DQ_CONFIG_PATH', raising=False)
    monkeypatch.setattr(sys, 'platform', 'win32')
    from app.web.app import _resolve_config_path
    result = _resolve_config_path(None)
    assert result == Path.home() / 'Documents' / 'DQ Workbench' / 'config.yml'


def test_platform_default_linux(monkeypatch):
    """On Linux (and macOS — both use the non-win32 branch), default is ~/.config/dq-workbench/config.yml."""
    monkeypatch.delenv('DQ_CONFIG_PATH', raising=False)
    monkeypatch.setattr(sys, 'platform', 'linux')
    from app.web.app import _resolve_config_path
    result = _resolve_config_path(None)
    assert result == Path.home() / '.config' / 'dq-workbench' / 'config.yml'


def test_write_blank_config_creates_file(tmp_path):
    """_write_blank_config writes a valid YAML file with expected keys."""
    import yaml
    from app.web.app import _write_blank_config
    target = tmp_path / 'sub' / 'config.yml'
    _write_blank_config(target)
    assert target.exists()
    with open(target) as f:
        data = yaml.safe_load(f)
    assert data['server']['base_url'] == ''
    assert data['server']['d2_token'] == ''
    assert data['server']['logging_level'] == 'INFO'
    assert data['server']['max_concurrent_requests'] == 5
    assert data['server']['max_results'] == 500
    assert data['analyzer_stages'] == []


def test_configure_app_unreachable_stores_warning(tmp_path):
    """ConfigManager raising ValueError with 'unreachable' → STARTUP_WARNING with 'warning' category."""
    cfg = tmp_path / "config.yml"
    cfg.write_text("server:\n  base_url: 'https://example.org'\n  d2_token: 'tok'\n")
    with patch('app.web.app.ConfigManager', side_effect=ValueError("DHIS2 server is unreachable: refused")):
        app = Flask(__name__)
        app.secret_key = 'test'
        _configure_app(app, str(cfg), skip_validation=False)
    msg, cat = app.config['STARTUP_WARNING']
    assert cat == 'warning'
    assert 'unreachable' in msg.lower() or 'reach' in msg.lower()
    assert app.config['SKIP_VALIDATION'] is True


def test_configure_app_auth_failed_stores_warning(tmp_path):
    """ConfigManager raising ValueError with 'rejected' → STARTUP_WARNING with 'warning' category."""
    cfg = tmp_path / "config.yml"
    cfg.write_text("server:\n  base_url: 'https://example.org'\n  d2_token: 'tok'\n")
    with patch('app.web.app.ConfigManager', side_effect=ValueError("API token was rejected by the server: 401")):
        app = Flask(__name__)
        app.secret_key = 'test'
        _configure_app(app, str(cfg), skip_validation=False)
    msg, cat = app.config['STARTUP_WARNING']
    assert cat == 'warning'
    assert app.config['SKIP_VALIDATION'] is True


def test_configure_app_coc_failure_stores_danger(tmp_path):
    """ConfigManager raising ValueError for COC check → STARTUP_WARNING with 'danger' category."""
    cfg = tmp_path / "config.yml"
    cfg.write_text("server:\n  base_url: 'https://example.org'\n  d2_token: 'tok'\n")
    with patch('app.web.app.ConfigManager',
               side_effect=ValueError("Default category option combo 'HllvX50cXC0' does not exist")):
        app = Flask(__name__)
        app.secret_key = 'test'
        _configure_app(app, str(cfg), skip_validation=False)
    msg, cat = app.config['STARTUP_WARNING']
    assert cat == 'danger'
    assert app.config['SKIP_VALIDATION'] is True


def test_configure_app_bare_exception_stores_danger(tmp_path):
    """ConfigManager raising a bare Exception (e.g. YAML parse error) → STARTUP_WARNING with 'danger' category."""
    cfg = tmp_path / "config.yml"
    cfg.write_text(": bad yaml: [")
    with patch('app.web.app.ConfigManager', side_effect=Exception("YAML parse error")):
        app = Flask(__name__)
        app.secret_key = 'test'
        _configure_app(app, str(cfg), skip_validation=False)
    msg, cat = app.config['STARTUP_WARNING']
    assert cat == 'danger'
    assert app.config['SKIP_VALIDATION'] is True


def test_configure_app_skip_validation_does_not_set_warning(tmp_path):
    """In skip_validation=True mode, no ConfigManager call is made, no STARTUP_WARNING set."""
    cfg = tmp_path / "config.yml"
    cfg.write_text("server:\n  base_url: ''\n  d2_token: ''\n")
    app = Flask(__name__)
    app.secret_key = 'test'
    _configure_app(app, str(cfg), skip_validation=True)
    assert 'STARTUP_WARNING' not in app.config
