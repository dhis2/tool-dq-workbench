# Config Path Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display the absolute path of the loaded config file prominently on the Edit Server Configuration page so users (especially on Windows) can locate it on disk.

**Architecture:** The route already loads `config_path`; we resolve it to an absolute path via `os.path.abspath`, pass it to the template as `config_path`, and render an info banner with a copy-to-clipboard button above the form.

**Tech Stack:** Python (os.path), Flask/Jinja2, Bootstrap 5, vanilla JS Clipboard API

---

## File Map

| File | Change |
|------|--------|
| `app/web/routes/edit_server.py` | Pass `config_path` (absolute) to both `render_template` calls |
| `app/web/templates/edit_server.html` | Add info banner with path and copy button above the form |
| `tests/test_web_index.py` | Add test asserting the config path appears in GET response |

---

### Task 1: Pass config path to template

**Files:**
- Modify: `app/web/routes/edit_server.py`
- Test: `tests/test_web_index.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_web_index.py` (use the existing `client_blank` fixture and `blank_config` fixture — `blank_config` returns the path to the temp config file):

```python
def test_edit_server_shows_config_path(client_blank, blank_config):
    """GET /api/edit-server must display the absolute config file path."""
    import os
    response = client_blank.get('/api/edit-server')
    assert os.path.abspath(blank_config).encode() in response.data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_web_index.py::test_edit_server_shows_config_path -v
```

Expected: FAIL — the path is not currently passed to the template.

- [ ] **Step 3: Update the route to pass the absolute path**

Edit `app/web/routes/edit_server.py`. Add `import os` at the top, then resolve the path and pass it to both `render_template` calls:

```python
import os

from flask import current_app, request, render_template, redirect, url_for, flash

from app.core.config_loader import ConfigManager
from app.web.routes.api import api_bp
from app.web.utils.config_helpers import save_config

@api_bp.route('/edit-server', methods=['GET', 'POST'], endpoint='edit_server')
def edit_server():
    config_path = current_app.config['CONFIG_PATH']
    abs_config_path = os.path.abspath(config_path)
    config = ConfigManager(config_path, config=None, validate_structure=False,
                           validate_runtime=False).config

    server = config.setdefault('server', {})
    server.setdefault('base_url', '')
    server.setdefault('d2_token', '')
    server.setdefault('logging_level', 'INFO')
    server.setdefault('max_concurrent_requests', 5)
    server.setdefault('max_results', 500)
    server.setdefault('min_max_bulk_api_disabled', False)

    if request.method == 'POST':

        try:
            config['server']['base_url'] = request.form['base_url']
            new_token = request.form['d2_token'].strip()
            if new_token:
                config['server']['d2_token'] = new_token
            config['server']['logging_level'] = request.form['logging_level']
            config['server']['max_concurrent_requests'] = int(request.form['max_concurrent_requests'])
            config['server']['max_results'] = int(request.form['max_results'])
            config['server']['min_max_bulk_api_disabled'] = (
                request.form.get('min_max_bulk_api_disabled', 'false').lower() == 'true'
            )

            save_config(config_path, config)
            flash('Server configuration updated.', 'success')
            return redirect(url_for('ui.index'))

        except ValueError as e:
            flash(f"Failed to save server configuration: {e}", 'danger')

        except Exception as e:
            flash(f"Unexpected error: {e}", 'danger')
            return redirect(url_for('ui.index'))

        return render_template("edit_server.html", server=config['server'],
                               config_path=abs_config_path)

    return render_template("edit_server.html", server=config['server'],
                           config_path=abs_config_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_web_index.py::test_edit_server_shows_config_path -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/test_web_index.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/web/routes/edit_server.py tests/test_web_index.py
git commit -m "feat: pass absolute config path to edit-server template"
```

---

### Task 2: Display the config path in the template

**Files:**
- Modify: `app/web/templates/edit_server.html`

No new test needed — the path is already covered by Task 1's test. The template change is pure presentation.

- [ ] **Step 1: Add the info banner to `edit_server.html`**

Insert the following block immediately after `{% include "partials/_flashes.html" %}` and before the `<h1>`:

```html
  <div class="alert alert-info d-flex align-items-center gap-2 mb-4" role="alert">
    <div class="flex-grow-1">
      <strong>Config file location:</strong>
      <code id="config-path-value">{{ config_path }}</code>
    </div>
    <button
      class="btn btn-sm btn-outline-secondary"
      type="button"
      onclick="
        navigator.clipboard.writeText(document.getElementById('config-path-value').innerText)
          .then(function() {
            var btn = event.currentTarget;
            var orig = btn.innerText;
            btn.innerText = 'Copied!';
            setTimeout(function() { btn.innerText = orig; }, 1500);
          });
      "
    >Copy path</button>
  </div>
```

The full updated template:

```html
{% extends "layout.html" %}

{% block content %}
{% include "partials/_flashes.html" %}

  <div class="alert alert-info d-flex align-items-center gap-2 mb-4" role="alert">
    <div class="flex-grow-1">
      <strong>Config file location:</strong>
      <code id="config-path-value">{{ config_path }}</code>
    </div>
    <button
      class="btn btn-sm btn-outline-secondary"
      type="button"
      onclick="
        navigator.clipboard.writeText(document.getElementById('config-path-value').innerText)
          .then(function() {
            var btn = event.currentTarget;
            var orig = btn.innerText;
            btn.innerText = 'Copied!';
            setTimeout(function() { btn.innerText = orig; }, 1500);
          });
      "
    >Copy path</button>
  </div>

  <h1>Edit Server Configuration</h1>

  <form method="post">
    <div class="mb-3">
      <label class="form-label" for="base_url">Base URL</label>
      <input class="form-control" id="base_url" name="base_url" value="{{ server.base_url }}">
    </div>
    <div class="mb-3">
      <label class="form-label" for="d2_token">API Token</label>
      <input class="form-control" id="d2_token" name="d2_token" placeholder="Enter new token (leave blank to keep existing)" type="password">
    </div>
    <div class="mb-3">
      <label class="form-label" for="logging_level">Logging Level</label>
      <select class="form-select" id="logging_level" name="logging_level">
        {% for level in ['DEBUG', 'INFO', 'WARNING', 'ERROR'] %}
          <option value="{{ level }}" {% if server.logging_level == level %}selected{% endif %}>{{ level }}</option>
        {% endfor %}
      </select>
    </div>
    <div class="mb-3">
      <label class="form-label" for="max_concurrent_requests">Max Concurrent Requests</label>
      <input class="form-control" id="max_concurrent_requests" name="max_concurrent_requests" type="number" value="{{ server.max_concurrent_requests }}">
    </div>
    <div class="mb-3">
      <label class="form-label" for="max_results">Max Results</label>
      <input class="form-control" id="max_results" name="max_results" type="number" value="{{ server.max_results }}">
    </div>
    <div class="mb-3">
      <label class="form-label" for="min_max_bulk_api_disabled">Disable bulk MinMax API</label>
      <select class="form-select" id="min_max_bulk_api_disabled" name="min_max_bulk_api_disabled">
        <option value="true" {% if server.min_max_bulk_api_disabled %}selected{% endif %}>Yes</option>
        <option value="false" {% if not server.min_max_bulk_api_disabled %}selected{% endif %}>No</option>
      </select>
    </div>
    <button class="btn btn-primary" type="submit">Save</button>
    <a class="btn btn-secondary" href="{{ url_for('ui.index') }}">Cancel</a>
  </form>
{% endblock %}
```

- [ ] **Step 2: Manual smoke test**

Start the app and navigate to the Edit Server Configuration page. Verify:
- The blue info banner appears above the heading with the full absolute path
- Clicking "Copy path" copies the text and the button momentarily reads "Copied!"

```bash
python dq_monitor.py --config config/sample_config.yml
```

- [ ] **Step 3: Commit**

```bash
git add app/web/templates/edit_server.html
git commit -m "feat: display config file path with copy button on edit-server page"
```