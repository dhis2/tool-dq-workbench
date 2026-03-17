import sys
import os
from pathlib import Path
import pytest


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
    assert data['analyzer_stages'] == []
