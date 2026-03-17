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
         patch('app.web.app.threading') as mock_threading:
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
    assert timer_args[0] == 1.5   # delay in seconds
