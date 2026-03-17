# Zero-Config Startup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the web UI to launch without a `--config` argument or pre-existing config file, redirecting first-time users to the server configuration page automatically.

**Architecture:** Three focused changes — fix `has_server` detection and add a first-run redirect in the index route; make the edit-server route tolerant of a blank config; and make `--config` optional in `main()` with a platform-default path and blank-config bootstrap.

**Tech Stack:** Python 3.10+, Flask, PyYAML, pathlib, pytest, Flask test client

---

## Chunk 1: Fix `index.py` — `has_server` check and first-run redirect

### Task 1: Write failing tests for index route first-run behaviour

**Files:**
- Create: `tests/test_web_index.py`

The existing tests don't cover Flask routes. We need a small pytest fixture that creates a minimal Flask test client backed by a temporary config file.

- [ ] **Step 1: Create `tests/test_web_index.py` with the fixture and two failing tests**

```python
# tests/test_web_index.py
import pytest
import yaml
from app.web.app import create_app


@pytest.fixture
def blank_config(tmp_path):
    """A config file with an empty server section — simulates first run."""
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
    return str(cfg)


@pytest.fixture
def populated_config(tmp_path):
    """A config file with real (fake) server credentials."""
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


@pytest.fixture
def client_blank(blank_config):
    app = create_app(blank_config, skip_validation=True)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def client_populated(populated_config):
    app = create_app(populated_config, skip_validation=True)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_blank_config_redirects_to_edit_server(client_blank):
    """First run with empty credentials should redirect to the server config page."""
    response = client_blank.get('/', follow_redirects=False)
    assert response.status_code == 302
    assert '/api/edit-server' in response.headers['Location']


def test_blank_config_redirect_shows_welcome_flash(client_blank):
    """The first-run redirect must include the welcome flash message."""
    response = client_blank.get('/', follow_redirects=True)
    assert b'Welcome' in response.data
    assert b'DHIS2 server details' in response.data


def test_populated_config_renders_dashboard(client_populated):
    """A config with real credentials should render the dashboard, not redirect."""
    response = client_populated.get('/', follow_redirects=False)
    assert response.status_code == 200
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest tests/test_web_index.py -v
```

Expected: `test_blank_config_redirects_to_edit_server` and `test_blank_config_redirect_shows_welcome_flash` FAIL (no redirect yet); `test_populated_config_renders_dashboard` should already pass.

### Task 2: Implement the `has_server` fix and redirect in `index.py`

**Files:**
- Modify: `app/web/routes/index.py`

- [ ] **Step 3: Update `has_server` to check for actual credentials, and add the redirect**

In `app/web/routes/index.py`, make two changes:

1. Change line 27 from:
```python
has_server = bool(server)
```
to:
```python
has_server = bool(server.get('base_url') and server.get('d2_token'))
```

2. Add the redirect after the `except` block, before `render_template`. The full function should end like this:

```python
    except Exception as e:
        load_error = str(e)

    if not load_error and not has_server:
        from flask import flash, redirect, url_for
        flash("Welcome — please enter your DHIS2 server details to get started.", "info")
        return redirect(url_for('api.edit_server'))

    return render_template(
        "index.html",
        ...
    )
```

Add `flash, redirect, url_for` to the existing import at the top of the file:
```python
from flask import current_app, flash, redirect, render_template, url_for
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/test_web_index.py -v
```

Expected: both PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
pytest
```

Expected: all 16 existing tests + 3 new tests pass (19 total)

- [ ] **Step 6: Commit**

```bash
git add app/web/routes/index.py tests/test_web_index.py
git commit -m "feat: redirect to server config on first run with blank credentials"
```

---

## Chunk 2: Fix `edit_server.py` — tolerate blank config

### Task 3: Write failing test for edit-server GET with blank config

**Files:**
- Modify: `tests/test_web_index.py` (add edit-server tests here — they share the same fixtures)

- [ ] **Step 1: Add a failing test for GET /api/edit-server with blank config**

Append to `tests/test_web_index.py`:

```python
def test_edit_server_get_with_blank_config(client_blank):
    """GET /api/edit-server must render without crashing when config has empty fields."""
    response = client_blank.get('/api/edit-server')
    assert response.status_code == 200
    assert b'Edit Server Configuration' in response.data
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/test_web_index.py::test_edit_server_get_with_blank_config -v
```

Expected: FAIL — `ConfigManager` raises because `validate_structure=True` rejects empty `base_url`.

### Task 4: Implement the `edit_server.py` fixes

**Files:**
- Modify: `app/web/routes/edit_server.py`

- [ ] **Step 3: Change `validate_structure=True` to `False` and add `setdefault` defaults**

The `ConfigManager` call is at the top of `edit_server()` (line 10), shared by both GET and POST. Change it:

```python
# Before
config = ConfigManager(config_path, config=None, validate_structure=True,
                       validate_runtime=False).config

# After
config = ConfigManager(config_path, config=None, validate_structure=False,
                       validate_runtime=False).config
```

Immediately after that line, add defaults so the template never sees missing keys:

```python
server = config.setdefault('server', {})
server.setdefault('base_url', '')
server.setdefault('d2_token', '')
server.setdefault('logging_level', 'INFO')
server.setdefault('max_concurrent_requests', 5)
server.setdefault('max_results', 500)
server.setdefault('min_max_bulk_api_disabled', False)
```

The rest of the function is unchanged — the POST handler reads `config['server']` which now has these defaults in place.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/test_web_index.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Run the full test suite**

```bash
pytest
```

Expected: all 20 tests pass

- [ ] **Step 6: Commit**

```bash
git add app/web/routes/edit_server.py tests/test_web_index.py
git commit -m "feat: make edit-server page tolerant of blank config on first run"
```

---

## Chunk 3: Update `app/web/app.py` — optional `--config` and path resolution

### Task 5: Extract and test config path resolution logic

**Files:**
- Modify: `app/web/app.py`
- Create: `tests/test_web_app_config.py`

The path resolution logic needs to be testable in isolation. Extract it into a standalone function `_resolve_config_path(cli_arg)` that takes the `--config` value (or `None`) and returns a `pathlib.Path`.

- [ ] **Step 1: Write failing tests for `_resolve_config_path`**

```python
# tests/test_web_app_config.py
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
pytest tests/test_web_app_config.py -v
```

Expected: FAIL — `_resolve_config_path` does not exist yet.

### Task 6: Implement `_resolve_config_path` and blank-config bootstrap

**Files:**
- Modify: `app/web/app.py`

- [ ] **Step 3: Add `_resolve_config_path` and `_write_blank_config` to `app/web/app.py`**

Add these two functions (anywhere above `main()`):

```python
def _resolve_config_path(cli_arg):
    """Resolve config path: CLI arg > DQ_CONFIG_PATH env var > platform default."""
    import sys
    from pathlib import Path
    if cli_arg:
        return Path(cli_arg)
    env = os.environ.get('DQ_CONFIG_PATH')
    if env:
        return Path(env)
    if sys.platform == 'win32':
        return Path.home() / 'Documents' / 'DQ Workbench' / 'config.yml'
    return Path.home() / '.config' / 'dq-workbench' / 'config.yml'


def _write_blank_config(path):
    """Write a minimal blank config to path, creating parent directories.

    Unlike the existing _bootstrap_config() (which takes real credentials for Docker),
    this writes an empty config for first-run onboarding — credentials are filled in
    via the web UI.
    """
    import yaml  # yaml is not imported at module level; use local import like _bootstrap_config
    path.parent.mkdir(parents=True, exist_ok=True)
    minimal = {
        'server': {
            'base_url': '',
            'd2_token': '',
            'logging_level': 'INFO',
            'max_concurrent_requests': 5,
            'max_results': 500,
        },
        'analyzer_stages': [],
    }
    with open(path, 'w') as f:
        yaml.dump(minimal, f, default_flow_style=False)
    logging.info(f"Created blank config at '{path}'")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/test_web_app_config.py -v
```

Expected: all 4 PASS

### Task 7: Write failing test for blank-config bootstrap

**Files:**
- Modify: `tests/test_web_app_config.py`

- [ ] **Step 5: Add a test for `_write_blank_config`**

```python
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
```

- [ ] **Step 6: Run the test to verify it passes** (it should pass since we just implemented the function)

```bash
pytest tests/test_web_app_config.py -v
```

Expected: all 5 PASS

### Task 8: Update `main()` to use the new helpers

**Files:**
- Modify: `app/web/app.py`

- [ ] **Step 7: Update `main()` — make `--config` optional and wire up path resolution**

Replace the existing `main()` function with:

```python
def main():
    parser = argparse.ArgumentParser(description="Flask UI for Data Quality Monitor")
    parser.add_argument('--config', default=None, help='Path to YAML config file (default: platform-appropriate location)')
    parser.add_argument('--skip-validation', action='store_true',
                        help='Skip config validation (use for onboarding only)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable Flask debug mode (development only)')
    args = parser.parse_args()

    config_path = _resolve_config_path(args.config)
    skip_validation = args.skip_validation

    if not config_path.exists():
        logging.info(f"No config found at '{config_path}'. Creating blank config.")
        _write_blank_config(config_path)
        skip_validation = True

    app = create_app(str(config_path), skip_validation=skip_validation)
    print(f"Using config: {app.config['CONFIG_PATH']}")

    if args.debug:
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        print("Registered routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule.endpoint}: {rule.rule}")

    app.run(debug=args.debug, use_reloader=False)
```

- [ ] **Step 8: Run the full test suite**

```bash
pytest
```

Expected: all tests pass (16 original + 3 index + 1 edit-server + 5 config = 25 total, assuming Chunks 1 and 2 have already been applied; expect 21 if running Chunk 3 alone)

- [ ] **Step 9: Commit**

```bash
git add app/web/app.py tests/test_web_app_config.py
git commit -m "feat: make --config optional with platform-default path and blank-config bootstrap"
```