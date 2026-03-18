# Version Update Notification — Design Spec

## Goal

Inform users that a newer version of DQ Workbench is available, displayed once on the first page they open after starting the app, then gone.

## Context

`_check_for_updates()` in `app/web/app.py` already runs once in a background thread on startup and compares the installed version against the latest GitHub release. Currently it only logs a warning. This spec covers surfacing that result in the web UI.

## Design

### Storage

Add a module-level variable in `app/web/app.py`:

```python
_available_update: str | None = None  # set by _check_for_updates(); read once by before_request hook
```

`_check_for_updates()` writes the latest tag string (e.g. `"0.9.12"`) to `_available_update` when a newer version is found. No other change to the existing check logic.

### Surfacing

Register a `before_request` hook inside `create_app()`. On the first request after startup, if `_available_update` is set, the hook:

1. Calls `flash()` with an `info` category and a message of the form:
   `"A newer version (v0.9.12) is available. Visit the releases page to update."`
2. Sets `_available_update = None` so the hook is effectively a no-op on every subsequent request.

The hook must declare `global _available_update` before assigning `None`; without it Python treats the assignment as a local variable and the message flashes on every request:

Flask auto-escapes flash message strings, so use `flask.Markup` to include a safe clickable link:

```python
from flask import Markup

@app.before_request
def _notify_if_update_available():
    global _available_update
    if _available_update:
        flash(
            Markup(
                f"A newer version (v{_available_update}) is available. "
                '<a href="https://github.com/dhis2/tool-dq-workbench/releases" '
                'class="alert-link" target="_blank" rel="noopener">Download it here.</a>'
            ),
            'info',
        )
        _available_update = None
```

### Display

No template changes required. `layout.html` already includes `partials/_flashes.html`, which renders all flash messages on every page. The `info` category maps to Bootstrap `alert-info` (blue), consistent with the config path banner added to `edit_server.html`.

The message appears on whatever page the user first loads in the browser and disappears after that render. Dismissal is inherent to Flask's flash system — messages are consumed on read.

## Files Changed

| File | Change |
|------|--------|
| `app/web/app.py` | Add `_available_update` module var; update `_check_for_updates()` to write to it; register `before_request` hook in `create_app()` |

No other files change.

## Out of Scope

- Persistent dismissal across restarts (not needed — check only runs once per startup anyway)
- Dashboard or other page-specific placement (server config page is sufficient)
- Continuous background polling (startup-only check is already in place)

## Testing

- Unit test: mock `_available_update` set to a version string; GET any page; assert flash message appears in response and contains the version string.
- Unit test: same setup; GET a second page; assert flash message does NOT appear (consumed on first render).
- Existing tests must continue to pass (the hook is a no-op when `_available_update` is None).
