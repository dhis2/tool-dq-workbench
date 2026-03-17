# Design: Integrity Checks Available Notification

**Date:** 2026-03-17
**Status:** Approved

## Overview

When a user opens the integrity stage edit/create page, proactively inform them if new or custom integrity checks are available in DHIS2 that do not yet have corresponding data elements configured. This surfaces the existing `get_integrity_checks_no_data_elements()` function to the user in a visible way.

## Scope

- Notification appears on the integrity stage edit/create page only (`stage_form_integrity_checks.html`)
- No changes to the index page or other routes

## Route Changes (`edit_integrity_stage.py`)

In `integrity_stage_view`, initialise `has_missing_checks = False` before the `if request.method == 'POST':` branch so it is always defined when `render_template` is called (both on GET and on a POST that fails validation and falls through to re-render).

On GET only (guarded by `if request.method == 'GET':`), construct an `IntegrityCheckAnalyzer` and call `get_integrity_checks_no_data_elements()`. The constructor requires all three arguments — `config`, `base_url`, and `headers` — mirroring the pattern already used in `create_missing_data_elements`:

```python
d2_token = config['server'].get('d2_token')
base_url = config['server']['base_url']
request_headers = {
    'Authorization': f'ApiToken {d2_token}',
    'Content-Type': 'application/json',
}
integrity_analyzer = IntegrityCheckAnalyzer(config, base_url=base_url, headers=request_headers)
```

**Error handling:**
- If the call succeeds and returns checks → `has_missing_checks=True`
- If the call succeeds and returns nothing → `has_missing_checks=False`
- If the call raises an exception → flash a warning (`'warning'` category: "Could not check for new integrity checks: ..."), leave `has_missing_checks=False`, page still renders normally
- The exception catch must use bare `Exception` (not `requests.exceptions.RequestException`) since `get_integrity_checks_no_data_elements()` calls through two internal helpers that may raise non-requests exceptions

On POST-with-validation-errors, the check does not re-run; `has_missing_checks` remains `False` and no alert is shown on re-render. This is acceptable — the user is focused on fixing the form error.

Pass `has_missing_checks` to `render_template` alongside the existing template variables.

## Template Changes (`stage_form_integrity_checks.html`)

Add a Bootstrap info alert between the `<hr>` separator and the existing "Create missing" form (i.e. directly above the button section at line 56), rendered only when `has_missing_checks` is true:

```html
{% if has_missing_checks %}
<div class="alert alert-info" role="alert">
  New integrity checks are available. Click below to create the missing data elements.
</div>
{% endif %}
```

Placing it here contextualises it immediately above the button it refers to, without interfering with the main stage configuration form above the `<hr>`.

The existing "Create missing integrity data elements" button remains enabled regardless of `has_missing_checks` — clicking it when nothing is missing is already a no-op (the route flashes "No missing data elements found").

## What is Not Changing

- The `create_missing_data_elements` route (`POST /integrity-stage/create-missing-des`) is unchanged
- The button label and behaviour are unchanged
- No new API endpoints or JavaScript
- No changes to the index page
