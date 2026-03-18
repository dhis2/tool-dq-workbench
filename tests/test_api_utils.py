from unittest.mock import patch, MagicMock
import requests

from app.core.api_utils import Dhis2ApiUtils


def _make_utils():
    return Dhis2ApiUtils('https://dhis2.example.org', 'fake-token')


def test_ping_ok():
    """HTTP 200 → ('ok', None)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch('requests.get', return_value=mock_resp):
        status, reason = _make_utils().ping()
    assert status == 'ok'
    assert reason is None


def test_ping_auth_failed():
    """HTTP 401 → ('auth_failed', reason string)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    with patch('requests.get', return_value=mock_resp):
        status, reason = _make_utils().ping()
    assert status == 'auth_failed'
    assert '401' in reason


def test_ping_unreachable():
    """ConnectionError → ('unreachable', reason string)."""
    with patch('requests.get', side_effect=requests.exceptions.ConnectionError('refused')):
        status, reason = _make_utils().ping()
    assert status == 'unreachable'
    assert reason is not None
