
# Design: Zero-Config Startup for Web UI

**Date:** 2026-03-17
**Status:** Approved

## Overview

Allow the web UI to launch without requiring a `--config` argument or a pre-existing config file. On first run the app creates a blank config at a platform-appropriate default path and redirects the user straight to the server configuration page. Technical users retain full control via `--config` and `DQ_CONFIG_PATH`.

This is a prerequisite for the Windows installer, where the app must be launchable by a double-click with no command-line interaction.

## Config Path Resolution

The config path is resolved in priority order:

1. `--config <path>` CLI argument (if provided)
2. `DQ_CONFIG_PATH` environment variable (if set) — this is a **new** variable introduced for the desktop use case; the existing `CONFIG_PATH` variable remains Docker/gunicorn-only and is unchanged
3. Platform default:
   - Windows: `~/Documents/DQ Workbench/config.yml`
   - Linux/Mac: `~/.config/dq-workbench/config.yml`

Platform detection uses `sys.platform` and `pathlib.Path.home()` — no new dependencies.

Note: the Windows default path contains a space. This is fine for Python's `pathlib`. Users who pass this path to `--config` on the command line must quote it.

## Changes: `app/web/app.py` — `main()`

- Remove `required=True` from the `--config` argument (default: `None`)
- After argument parsing, resolve the config path using the priority order above
- If the resolved file does not exist:
  - Create parent directories
  - Write a minimal blank config (see below)
  - **Call `create_app(config_path, skip_validation=True)`** — this is required because `_configure_app` calls `ConfigManager` internally, which performs a live network call to DHIS2 when `skip_validation=False`. With a blank config there are no credentials to validate against.
- If the resolved file exists, start the app normally: `skip_validation` is controlled by the `--skip-validation` flag as today

### Blank Config

When bootstrapping a missing config, write:

```yaml
server:
  base_url: ''
  d2_token: ''
  logging_level: INFO
  max_concurrent_requests: 5
  max_results: 500
analyzer_stages: []
```

`min_max_stages` is intentionally omitted — consistent with the existing `_bootstrap_config` Docker helper, which also omits it. Structural validation does not require it.

A future "Validate config" button in the UI (not in scope here) can provide on-demand connectivity checking once credentials are entered.

## Changes: `app/web/routes/index.py`

`has_server` currently checks `bool(server)`, which is `True` for any non-empty dict — including the blank config, which has a `server` key with empty strings. The check must be updated to verify that actual credentials are present:

```python
has_server = bool(server.get('base_url') and server.get('d2_token'))
```

When `has_server` is `False` **and the config loaded without errors** (i.e. `load_error` is `None`), redirect to the edit server page:

```python
if not load_error and not has_server:
    flash("Welcome — please enter your DHIS2 server details to get started.", "info")
    return redirect(url_for('api.edit_server'))
```

The `load_error` guard ensures the redirect does not fire when the YAML is corrupt or unreadable — in that case the existing error display behaviour is preserved. The redirect target `url_for('api.edit_server')` is correct: `edit_server.py` registers on the `api` blueprint with `endpoint='edit_server'`.

## Changes: `app/web/routes/edit_server.py`

The `ConfigManager` call at the top of `edit_server()` is shared by both GET and POST (it runs before the `if request.method == 'POST':` branch). Two fixes:

1. **Change `validate_structure=True` to `validate_structure=False`** — this applies to both GET and POST paths since the load is shared. Note: `validate_structure=True` triggers `_validate_api_token`, which makes a live HTTP request to `/api/me`. Switching to `False` eliminates that hidden network call, which is the intended behaviour — connectivity checking on this route is not appropriate.

2. **Default missing server fields before rendering** — after loading, fill any missing keys with safe defaults before passing to the template:

```python
server = config.get('server') or {}
server.setdefault('base_url', '')
server.setdefault('d2_token', '')
server.setdefault('logging_level', 'INFO')
server.setdefault('max_concurrent_requests', 5)
server.setdefault('max_results', 500)
server.setdefault('min_max_bulk_api_disabled', False)
```

This prevents Jinja2 `UndefinedError` when rendering a blank config on first run.

The POST handler's save logic is unchanged — it already skips updating `d2_token` if the submitted value is blank, and writes correctly into a previously empty server section.

## What is Not Changing

- Docker/gunicorn path (`create_app_from_env()`) is unchanged
- `CONFIG_PATH` environment variable (Docker-only) is unchanged
- `--skip-validation` flag behaviour for technical users is unchanged
- The `--config` argument continues to work exactly as today when provided
- No runtime DHIS2 connectivity validation is added at startup (deferred to future "Validate config" button)
