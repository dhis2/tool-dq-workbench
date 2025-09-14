import logging
import requests
from typing import Any, Dict, Mapping, Optional, List
from copy import deepcopy
from flask import current_app, request, render_template, redirect, url_for, flash

from app.analyzers.integrity_analyzer import IntegrityCheckAnalyzer
from app.core.api_utils import Dhis2ApiUtils
from app.web.utils.config_helpers import save_config
from app.web.routes.api import api_bp
from app.core.config_loader import ConfigManager
from app.core.uid_utils import UidUtils


# -------------------- defaults & validation --------------------

def default_integrity_stage() -> Dict[str, Any]:
    """Utility to generate a blank integrity stage"""
    uid = UidUtils.generate_uid()
    return {
        'name': '',
        'uid': uid,
        'active': True,
        'type': 'integrity_checks',
        'level': 1,
        'params': {
            'monitoring_group': '',
            'period_type': 'Monthly',
            'dataset': ''
        }
    }

def validate_integrity_stage(stage: Dict[str, Any]) -> None:
    """Validate integrity stage configuration"""
    if not stage.get('name'):
        raise ValueError("Stage name cannot be empty")
    if not stage.get('uid'):
        raise ValueError("Stage UID cannot be empty")
    params = stage.get('params', {})
    if not params.get('monitoring_group'):
        raise ValueError("Monitoring group must be specified")
    if not params.get('period_type'):
        raise ValueError("Period type must be specified")


# --------------------Helpers--------------------

def _load_config(path: str) -> Dict[str, Any]:
    cm = ConfigManager(config_path=path, config=None, validate_structure=True, validate_runtime=False)
    return cm.config

def _validate_and_save_config(path: str, config: Dict[str, Any]) -> None:
    # Validate structure before persisting
    ConfigManager(config_path=None, config=config, validate_structure=True, validate_runtime=False)
    save_config(path, config)

def _api_utils_from_config(config: Dict[str, Any]) -> Dhis2ApiUtils:
    server = config.get('server', {})
    return Dhis2ApiUtils(
        base_url=server['base_url'],
        d2_token=server['d2_token'],
    )

def _stage_for_edit(config: Dict[str, Any], idx: int) -> Dict[str, Any]:
    stages: List[Dict[str, Any]] = config.get('analyzer_stages') or []
    if not (0 <= idx < len(stages)):
        raise ValueError("Stage not found.")
    stage = stages[idx]
    if stage.get('type') != 'integrity_checks':
        raise ValueError('Only the integrity check stage can be edited here.')
    return stage

def _ensure_analyzer_stages_list(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    if 'analyzer_stages' not in config or not isinstance(config['analyzer_stages'], list):
        config['analyzer_stages'] = []
    return config['analyzer_stages']

def _apply_form_to_integrity_stage(stage: Dict[str, Any], form: Mapping[str, str], is_edit: bool) -> None:
    def as_int(key: str, default: Optional[int] = None) -> Optional[int]:
        v = form.get(key)
        try:
            return int(v) if v not in (None, "") else default
        except (TypeError, ValueError):
            return default

    def as_str(key: str, default: Optional[str] = None) -> Optional[str]:
        v = form.get(key, default)
        return v if v not in ("",) else default

    params = stage.setdefault('params', {})

    stage['name'] = as_str('stage_name', stage.get('name'))
    params['level'] = as_int('orgunit_level', params.get('level'))
    params['duration'] = as_str('duration', params.get('duration'))
    params['monitoring_group'] = as_str('monitoring_group', params.get('monitoring_group'))
    params['period_type'] = as_str('period_type', params.get('period_type'))

    # UID handling
    if not is_edit and not stage.get('uid'):
        stage['uid'] = UidUtils.generate_uid()
    elif is_edit and stage.get('uid'):
        stage['uid'] = stage['uid'].strip()

    # Active flag (edit-only)
    if is_edit:
        logging.debug("Stage active status: %s", form.get('active', 'off'))
        stage['active'] = (form.get('active', 'off') == 'on')

def get_data_element_group_name(api_utils: Dhis2ApiUtils, deg_uid: str) -> str:
    """Fetch data element group name, return UID if fetch fails"""
    if not deg_uid:
        return ''
    try:
        deg = api_utils.fetch_data_element_group_by_id(deg_uid)
        name = (deg or {}).get('name') or deg_uid
        logging.debug("Fetched data element group name: %s", name)
        return name
    except requests.exceptions.RequestException:
        flash(f"Warning: Failed to fetch data element group name for {deg_uid}", 'warning')
        return deg_uid

def _build_de_payload(check):
    code = str(check.get('code', '') or '')
    display_name = str(check.get('displayName', '') or '')
    return {
        "name": f"[MI] {display_name}",
        "shortName": f"[MI] {display_name[:40]}",  # DHIS2 shortName max 50 chars
        "code": f"MI_{code}",
        "valueType": "INTEGER",
        "domainType": "AGGREGATE",
        "aggregationType": "LAST",
        "zeroIsSignificant": True,
    }


# -------------------- controllers --------------------

@api_bp.route('/integrity-stage', methods=['GET', 'POST'], endpoint='new_integrity_stage')
@api_bp.route('/integrity-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_integrity_stage')
def integrity_stage_view(stage_index: Optional[int] = None):
    config_path = current_app.config['CONFIG_PATH']

    # Load config
    try:
        config = _load_config(config_path)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    is_edit = stage_index is not None

    # Get stage (existing or default)
    try:
        stage = _stage_for_edit(config, int(stage_index)) if is_edit else default_integrity_stage()
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    # API utils (only for rendering names / feedback)
    api_utils = _api_utils_from_config(config)

    # Resolve DE group name for display
    deg_uid = stage.get('params', {}).get('monitoring_group', '')
    deg_name = get_data_element_group_name(api_utils, deg_uid) if deg_uid else ''

    if request.method == 'POST':
        _apply_form_to_integrity_stage(stage, request.form, is_edit)

        # Update display name if UID changed (useful for feedback)
        new_deg_uid = request.form.get('monitoring_group', '')
        if new_deg_uid and new_deg_uid != deg_uid:
            deg_name = get_data_element_group_name(api_utils, new_deg_uid)
            if not is_edit:
                stage.setdefault('params', {})['dataelement_group_name'] = deg_name

        try:
            # Validate stage
            validate_integrity_stage(stage)

            # Append to config if creating
            if not is_edit:
                _ensure_analyzer_stages_list(config).append(stage)

            # Persist
            _validate_and_save_config(config_path, config)

            action = "Updated" if is_edit else "Added"
            flash(f"{action} integrity stage: {stage['name']}", 'success')
            return redirect(url_for('ui.index'))

        except ValueError as e:
            flash(f"Error saving stage: {e}", 'danger')
            # fall through to re-render with errors

    # Render form (GET or POST with validation errors)
    return render_template(
        "stage_form_integrity_checks.html",
        stage=deepcopy(stage) if is_edit else stage,
        edit=is_edit,
        deg_name=deg_name
    )

@api_bp.route('/integrity-stage/create-missing-des', methods=['POST'], endpoint='create_missing_des')
def create_missing_data_elements():
    """
    Create any missing data elements for integrity checks.
    Always return to the page that initiated the action so flashes are visible there.
    """
    # Prefer explicit 'next', then referrer, then fall back to edit view, then index
    stage_idx = request.form.get('stage_index')
    next_url = (
        request.form.get('next')
        or request.referrer
        or (url_for('api.edit_integrity_stage', stage_index=stage_idx) if stage_idx else None)
        or url_for('ui.index')
    )

    config_path = current_app.config['CONFIG_PATH']
    try:
        config = _load_config(config_path)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(next_url)

    api_utils = _api_utils_from_config(config)

    # Integrity analyzer setup
    d2_token = config['server'].get('d2_token')
    base_url = config['server']['base_url']
    request_headers = {
        'Authorization': f'ApiToken {d2_token}',
        'Content-Type': 'application/json',  # OK for POSTs below
    }
    integrity_analyzer = IntegrityCheckAnalyzer(config, base_url=base_url, headers=request_headers)

    # Find missing checks
    try:
        missing_checks = integrity_analyzer.get_integrity_checks_no_data_elements()
    except Exception as e:
        flash(f"Could not retrieve integrity checks: {e}", 'danger')
        return redirect(next_url)

    if not missing_checks:
        flash("No missing data elements found for integrity checks.", 'info')
        return redirect(next_url)

    # Build payload and create
    missing_des = [_build_de_payload(check) for check in missing_checks]

    try:
        payload = {"dataElements": missing_des}
        resp = api_utils.post_metadata(payload)  # if this returns a requests.Response
        if resp is None:
            flash("No response received from DHIS2. Please check the logs for details.", 'warning')
            return redirect(next_url)

        if hasattr(resp, "status_code"):  # Response-like
            if resp.status_code == 200:
                body = resp.json()
                stats = body.get('response', {}).get('stats', {})
                created_count = stats.get('created', 0)
                ignored_count = stats.get('ignored', 0)
                flash(f"Created {created_count} new data elements, {ignored_count} ignored.", 'success')
            elif resp.status_code == 409:
                error_msg = resp.json().get('message', 'Conflict occurred while creating data elements.')
                flash(f"DHIS2 returned a conflict (409): {error_msg}", 'warning')
            else:
                flash(f"Unexpected response from DHIS2: {resp.status_code}", 'warning')
        else:
            # If post_metadata already returns parsed JSON
            stats = resp.get('response', {}).get('stats', {}) if isinstance(resp, dict) else {}
            created_count = stats.get('created', 0)
            ignored_count = stats.get('ignored', 0)
            flash(f"Created {created_count} new data elements, {ignored_count} ignored.", 'success')

    except requests.exceptions.RequestException as e:
        flash(f"Error creating data elements: {e}", 'danger')

    return redirect(next_url)
