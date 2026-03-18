# Graceful Startup Degradation — Design Spec

## Goal

The Flask web app must never hard-crash on startup due to a bad config or connectivity failure. All problems are caught, surfaced as a flash message, and the user is redirected to the server configuration page to fix them.

## Context

Windows non-technical users double-click the app. If startup validation fails, the process dies silently — no explanation, no path forward. The root cause is `_configure_app()` in `app/web/app.py`, which re-raises all `ConfigManager` exceptions as `RuntimeError`, killing the process before Flask can serve any response.

Three failure scenarios need to be handled gracefully:

| Scenario | Current behaviour | Target behaviour |
|---|---|---|
| Config file unreadable (bad YAML, file missing) | Hard crash | Redirect to edit-server with `danger` flash |
| Server unreachable (network failure, bad base URL) | Hard crash | Redirect to edit-server with `warning` flash |
| Token invalid (server responds with 4xx) | Hard crash | Redirect to edit-server with `warning` flash |

## Design

### 1. `app/core/api_utils.py` — structured connectivity check

Replace the boolean `ping()` with a method that distinguishes three outcomes:

```python
def ping(self) -> tuple[str, str | None]:
    """
    Returns:
        ('ok', None)                — connected and authenticated
        ('unreachable', reason)     — network/connection failure
        ('auth_failed', reason)     — server responded but rejected the token (4xx)
    """
    try:
        response = requests.get(
            f"{self.base_url}/api/me",
            headers=self.request_headers,
            timeout=5,
        )
        if response.status_code == 200:
            return ('ok', None)
        return ('auth_failed', f"Server returned HTTP {response.status_code}")
    except requests.exceptions.RequestException as e:
        return ('unreachable', str(e))
```

Any caller that currently checks `if not api_utils.ping()` must be updated to unpack the tuple and check `status != 'ok'`. The only such caller is `config_loader.py:_validate_runtime()`. Note: `_validate_api_token()` in `validate_structure()` makes its own independent HTTP call and is unaffected — it is not invoked during web startup because `_configure_app()` calls `ConfigManager` with `validate_structure=False`.

### 2. `app/core/config_loader.py` — update `_validate_runtime()` caller

Update the `ping()` call to use the new return value:

```python
status, reason = api_utils.ping()
if status == 'unreachable':
    raise ValueError(f"DHIS2 server is unreachable: {reason}")
if status == 'auth_failed':
    raise ValueError(f"API token was rejected by the server: {reason}")
```

No other change to `ConfigManager`. The ValueError messages now distinguish the two failure modes, which `_configure_app()` uses to pick the right flash category and message.

### 3. `app/web/app.py` — `_configure_app()` never raises

Restructure `_configure_app()` to catch all failures and store them in `app.config['STARTUP_WARNING']` as a `(message, category)` tuple. Never raise. The app always starts.

```python
def _configure_app(app, config_path, skip_validation):
    config_path = os.path.abspath(config_path)
    app.config['CONFIG_PATH'] = config_path
    app.config['SKIP_VALIDATION'] = skip_validation

    if skip_validation:
        return  # onboarding mode — no validation needed

    try:
        ConfigManager(
            config_path,
            config=None,
            validate_structure=False,
            validate_runtime=True,
        )
    except ValueError as e:
        msg = str(e)
        if 'unreachable' in msg:
            app.config['STARTUP_WARNING'] = (
                "Could not reach the DHIS2 server — check that your base URL is correct.",
                'warning',
            )
        elif 'token' in msg.lower() or 'auth' in msg.lower() or 'rejected' in msg.lower():
            app.config['STARTUP_WARNING'] = (
                "Your API token was rejected. The server is reachable but authentication "
                "failed. Please enter a new token.",
                'warning',
            )
        else:
            app.config['STARTUP_WARNING'] = (
                f"Configuration problem: {msg}",
                'danger',
            )
        app.config['SKIP_VALIDATION'] = True
        logging.warning("Startup validation failed (graceful degradation): %s", msg)
    except Exception as e:
        # Unexpected error (e.g. YAML parse failure, file not found)
        app.config['STARTUP_WARNING'] = (
            f"Your config file could not be read: {e}. "
            f"Please check the file at {config_path}.",
            'danger',
        )
        app.config['SKIP_VALIDATION'] = True
        logging.error("Failed to load config at startup (graceful degradation): %s", e)
```

### 4. `app/web/routes/index.py` — redirect on `STARTUP_WARNING`

Add a check for `STARTUP_WARNING` **before** the existing `has_server` check. If both conditions are true (e.g. a corrupt config that also has a blank URL), the startup warning is more specific and actionable — it must not be swallowed by the generic "Welcome" redirect:

```python
startup_warning = current_app.config.pop('STARTUP_WARNING', None)
if startup_warning:
    message, category = startup_warning
    flash(message, category)
    return redirect(url_for('api.edit_server'))

if not load_error and not has_server:
    flash("Welcome — please enter your DHIS2 server details to get started.", "info")
    return redirect(url_for('api.edit_server'))
```

`pop()` clears the warning from shared app config after the first request reads it. This is **not** equivalent to Flask's session-based `flash()` (which is per-user). It works correctly because the app runs as a single-worker process (Waitress desktop mode). In a multi-worker deployment, a concurrent request could consume the warning before the user's browser receives it — but that is not a supported configuration.

### 5. `app/web/routes/edit_server.py` — guard against unreadable config

The route currently calls `ConfigManager(config_path, ...).config`. If the config file cannot be parsed at all, this will raise and crash the edit-server page — exactly where the user is trying to fix things.

Wrap it in a try/except that falls back to an empty server dict:

```python
try:
    config = ConfigManager(config_path, config=None, validate_structure=False,
                           validate_runtime=False).config
except Exception:
    config = {}

server = config.setdefault('server', {})
server.setdefault('base_url', '')
# ... etc (existing defaulting logic unchanged)
```

## Files Changed

| File | Change |
|---|---|
| `app/core/api_utils.py` | `ping()` returns `tuple[str, str \| None]` instead of `bool` |
| `app/core/config_loader.py` | Update `_validate_runtime()` to unpack new `ping()` return value |
| `app/web/app.py` | `_configure_app()` catches all failures, stores `STARTUP_WARNING`, never raises |
| `app/web/routes/index.py` | Check `STARTUP_WARNING`, flash and redirect to edit-server |
| `app/web/routes/edit_server.py` | Guard `ConfigManager` call against unreadable config |

## Out of Scope

- CLI mode (`app/cli.py`) — hard crash on bad config is acceptable there; the operator can read the terminal output
- `create_app_from_env()` Docker path — Docker deployments have operator-managed configs; graceful degradation is less critical and can be addressed separately
- Persistent error state across restarts — `STARTUP_WARNING` fires once per startup, which is sufficient

## Testing

**`ping()` return values:**
- Mock HTTP 200 → `('ok', None)`
- Mock HTTP 401 → `('auth_failed', 'Server returned HTTP 401')`
- Mock `ConnectionError` → `('unreachable', ...)`

**`_configure_app()` error categorisation:**
- Mock `ConfigManager` raising `ValueError("DHIS2 server is unreachable: ...")` → `STARTUP_WARNING` set with `'warning'` category, no exception raised
- Mock `ConfigManager` raising `ValueError("API token was rejected...")` → `STARTUP_WARNING` set with `'warning'` category
- Mock `ConfigManager` raising `ValueError("Default category option combo '...' does not exist")` (from `_validate_default_coc`) → `STARTUP_WARNING` set with `'danger'` category (falls through to `else` branch — server was reachable and token valid, but COC check failed)
- Mock `ConfigManager` raising a bare `Exception("YAML parse error")` → `STARTUP_WARNING` set with `'danger'` category

**`index.py` redirect behaviour:**
- GET `/` with `STARTUP_WARNING` pre-set → 302 redirect to edit-server, flash message in response, `STARTUP_WARNING` cleared from `app.config`
- GET `/` with `STARTUP_WARNING` pre-set AND blank `base_url` → `STARTUP_WARNING` fires (not the "Welcome" redirect), confirming check ordering

**`edit_server` resilience:**
- GET `/api/edit-server` with a config path pointing to an unparseable file → 200, blank form renders, no crash
