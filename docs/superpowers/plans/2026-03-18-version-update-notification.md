# Version Update Notification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a one-time flash notification on the first page load after startup when a newer version of DQ Workbench is available on GitHub.

**Architecture:** Add a module-level `_available_update` variable to `app/web/app.py`. The existing `_check_for_updates()` background thread writes the latest version tag to it when a newer version is found. A `before_request` hook registered in `create_app()` reads the variable, flashes a message with a link to the releases page, and clears the variable — so the message appears exactly once per process lifetime.

**Tech Stack:** Python, Flask (`flash`, `before_request`), `markupsafe.Markup` (Flask dependency, for HTML-safe flash content)

---

## File Map

| File | Change |
|------|--------|
| `app/web/app.py` | Add `_available_update` module var; write to it in `_check_for_updates()`; register `before_request` hook in `create_app()` |
| `tests/test_web_index.py` | Add two tests: flash appears on first load, does not appear on second load |

---

### Task 1: Surface version update as a one-time flash notification

**Files:**
- Modify: `app/web/app.py`
- Test: `tests/test_web_index.py`

Everything lives in one task because the observable behavior (flash on first request, not on second) requires both the storage variable and the hook to be in place before any test can pass.

- [ ] **Step 1: Write the two failing tests**

Add to `tests/test_web_index.py`, after the existing imports (the file already imports `pytest`, `yaml`, `os`, and `from app.web.app import create_app`):

```python
def test_update_notification_shown_on_first_request(client_blank):
    """If a newer version is available, flash message appears on first page load."""
    import app.web.app as app_module
    app_module._available_update = "9.9.9"
    try:
        response = client_blank.get('/', follow_redirects=True)
        assert b'9.9.9' in response.data
        assert b'github.com/dhis2/tool-dq-workbench/releases' in response.data
    finally:
        app_module._available_update = None


def test_update_notification_shown_only_once(client_blank):
    """Update flash message must not appear on the second request."""
    import app.web.app as app_module
    app_module._available_update = "9.9.9"
    try:
        client_blank.get('/', follow_redirects=True)   # first request consumes it
        response = client_blank.get('/', follow_redirects=True)  # second request
        assert b'9.9.9' not in response.data
    finally:
        app_module._available_update = None
```

Note: `client_blank` fixture already exists in the file — it creates a test Flask app with a blank config. The `follow_redirects=True` is needed because `GET /` with a blank config redirects to `/api/edit-server`, and the flash is rendered on the redirected page.

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_web_index.py::test_update_notification_shown_on_first_request tests/test_web_index.py::test_update_notification_shown_only_once -v
```

Expected: both FAIL — `_available_update` attribute does not exist yet.

- [ ] **Step 3: Add the module-level variable**

At the top of `app/web/app.py`, after the existing imports and before any function definitions, add:

```python
_available_update: str | None = None  # set by _check_for_updates(); read once by before_request hook
```

- [ ] **Step 4: Write to it from `_check_for_updates()`**

Inside `_check_for_updates()`, the nested `_do_check()` function ends with this block:

```python
            if _parse(latest_tag) > _parse(current):
                logging.warning(
                    f"A newer version (v{latest_tag}) is available. "
                    "Visit https://github.com/dhis2/tool-dq-workbench/releases to update."
                )
```

Replace the **entire `if _parse(latest_tag) > _parse(current):` block** with:

```python
            if _parse(latest_tag) > _parse(current):
                global _available_update
                _available_update = latest_tag
                logging.warning(
                    f"A newer version (v{latest_tag}) is available. "
                    "Visit https://github.com/dhis2/tool-dq-workbench/releases to update."
                )
```

`global _available_update` inside the nested `_do_check` correctly refers to the module-level variable (Python's `global` always means module scope, regardless of nesting depth). Keep the existing `logging.warning` — it's useful for server logs.

- [ ] **Step 5: Register the `before_request` hook in `create_app()`**

In `create_app()`, after `register_routes(app)` and before `return app`, add:

```python
    from markupsafe import Markup  # preferred over flask.Markup, which was deprecated in Flask 2.0

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

`markupsafe` is a direct Flask dependency and is always available. `Markup` marks the string as HTML-safe so Jinja2 does not escape the `<a>` tag. `flash` is already imported at the top of `app.py`.

- [ ] **Step 6: Run the two new tests**

```bash
pytest tests/test_web_index.py::test_update_notification_shown_on_first_request tests/test_web_index.py::test_update_notification_shown_only_once -v
```

Expected: both PASS.

- [ ] **Step 7: Run the full test suite to check for regressions**

```bash
pytest tests/test_web_index.py -v
```

Expected: all 8 tests pass (6 existing + 2 new).

- [ ] **Step 8: Commit**

```bash
git add app/web/app.py tests/test_web_index.py
git commit -m "feat: show one-time flash notification when newer version is available"
```
