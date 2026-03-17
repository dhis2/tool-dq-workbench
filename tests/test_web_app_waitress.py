# tests/test_web_app_waitress.py
import sys
import yaml
import pytest
from unittest.mock import patch, call


@pytest.fixture
def config_file(tmp_path):
    cfg = tmp_path / "config.yml"
    cfg.write_text(yaml.dump({
        'server': {
            'base_url': 'https://dhis2.example.org',
            'd2_token': 'fake-token',
            'logging_level': 'INFO',
            'max_concurrent_requests': 5,
            'max_results': 500,
        },
        'analyzer_stages': [],
    }))
    return str(cfg)


def test_main_serves_via_waitress(config_file, monkeypatch):
    """main() must use waitress.serve, not app.run()."""
    monkeypatch.setattr(sys, 'argv', ['prog', '--config', config_file, '--skip-validation'])
    with patch('app.web.app.serve') as mock_serve, \
         patch('app.web.app.threading'):
        from app.web.app import main
        main()
    mock_serve.assert_called_once()
    _, kwargs = mock_serve.call_args
    assert kwargs['host'] == '127.0.0.1'
    assert kwargs['port'] == 5000


def test_main_opens_browser(config_file, monkeypatch):
    """main() must schedule a browser open via threading.Timer."""
    monkeypatch.setattr(sys, 'argv', ['prog', '--config', config_file, '--skip-validation'])
    with patch('app.web.app.serve'), \
         patch('app.web.app.threading') as mock_threading:
        from app.web.app import main
        main()
    mock_threading.Timer.assert_called_once()
    timer_args = mock_threading.Timer.call_args[0]
    assert isinstance(timer_args[0], (int, float)) and timer_args[0] > 0  # positive delay in seconds


def test_create_app_uses_bundle_paths_when_frozen(tmp_path, monkeypatch):
    """create_app() must use bundle paths for templates/static when sys.frozen is set."""
    import os
    cfg = tmp_path / "config.yml"
    cfg.write_text(yaml.dump({
        'server': {
            'base_url': '',
            'd2_token': '',
            'logging_level': 'INFO',
            'max_concurrent_requests': 5,
            'max_results': 500,
        },
        'analyzer_stages': [],
    }))
    fake_bundle_dir = str(tmp_path / 'bundle')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', fake_bundle_dir, raising=False)

    from app.web.app import create_app
    flask_app = create_app(str(cfg), skip_validation=True)

    assert flask_app.template_folder == os.path.join(fake_bundle_dir, 'app', 'web', 'templates')
    assert flask_app.static_folder == os.path.join(fake_bundle_dir, 'app', 'web', 'static')


def test_create_app_uses_normal_paths_when_not_frozen(tmp_path, monkeypatch):
    """create_app() must use standard Flask paths when not running as a bundle."""
    cfg = tmp_path / "config.yml"
    cfg.write_text(yaml.dump({
        'server': {
            'base_url': '',
            'd2_token': '',
            'logging_level': 'INFO',
            'max_concurrent_requests': 5,
            'max_results': 500,
        },
        'analyzer_stages': [],
    }))
    monkeypatch.delattr(sys, 'frozen', raising=False)

    from app.web.app import create_app
    flask_app = create_app(str(cfg), skip_validation=True)

    # Flask default: template_folder is 'templates' (relative)
    assert flask_app.template_folder == 'templates'
