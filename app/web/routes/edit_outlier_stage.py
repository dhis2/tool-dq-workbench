import logging
from copy import deepcopy
from typing import Any, Mapping, Dict, Optional

import requests
from flask import current_app, request, redirect, url_for, flash, render_template

from app.core.api_utils import Dhis2ApiUtils
from app.core.config_loader import ConfigManager
from app.core.uid_utils import UidUtils
from app.web.routes.api import api_bp
from app.web.utils.config_helpers import save_config

# --- helpers ---------------------------------------------------------------
def default_outlier_stage():
    return {
        'name': '',
        'type': 'outlier',


        'params': {
            'level': 1,
            'duration': '12 months',
            'dataset': '',
            'algorithm': 'MOD_Z_SCORE',
            'threshold': 3,
            'destination_data_element': '',
            'start_date_offset': '',
            'end_date_offset': ''
        }
    }

def resolve_name(fetch_func, uid):
    if not uid:
        return ''
    try:
        result = fetch_func(uid)
        if result is None:
            flash(f"Warning: No result found for UID {uid}", 'warning')
            return uid
        return result.get('name') or uid
    except requests.exceptions.RequestException:
        flash(f"Warning: Failed to fetch name for {uid}", 'warning')
        return uid

def _load_config(path: str) -> Dict[str, Any]:
    cm = ConfigManager(config_path=path, config=None, validate_structure=True, validate_runtime=False)
    return cm.config

def _validate_and_save_config(path: str, config: Dict[str, Any]) -> None:
    ConfigManager(config_path=None, config=config, validate_structure=True, validate_runtime=False)
    save_config(path, config)

def _stage_for_edit(config: Dict[str, Any], idx: int) -> Dict[str, Any]:
    stages = config.get('analyzer_stages') or []
    if not (0 <= idx < len(stages)):
        raise ValueError("Invalid stage index.")
    stage = stages[idx]
    if stage.get('type') != 'outlier':
        raise ValueError('Only outlier stages can be edited here.')
    return stage

def _resolve_outlier_stage_references(config, stage):
    api_utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )
    de_uid = stage['params'].get('destination_data_element')
    ds_uid = stage['params'].get('dataset')
    monitoring_group_uid = stage['params'].get('monitoring_group')
    de_name = resolve_name(api_utils.fetch_data_element_by_id, de_uid)
    ds_name = resolve_name(api_utils.fetch_dataset_by_id, ds_uid)
    deg_name = resolve_name(api_utils.fetch_data_element_group_by_id, monitoring_group_uid)
    return de_name, deg_name, ds_name

def _apply_form_to_stage(stage: Dict[str, Any], form: Mapping[str, str], is_edit: bool) -> None:
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
    params.update({
        'level': as_int('orgunit_level', params.get('level')),
        'duration': as_str('duration', params.get('duration')),
        'dataset': as_str('dataset', params.get('dataset')),
        'algorithm': as_str('algorithm', params.get('algorithm')),
        'threshold': as_int('threshold', params.get('threshold')),
        'destination_data_element': as_str('destination_data_element', params.get('destination_data_element')),
        'start_date_offset': as_str('start_date_offset', params.get('start_date_offset')),
        'end_date_offset': as_str('end_date_offset', params.get('end_date_offset')),
    })

    if (not is_edit) or (not stage.get('uid')):
        stage['uid'] = UidUtils.generate_uid()
    if is_edit:
        logging.debug("Stage active status: %s", form.get('active', 'off'))
        stage['active'] = (form.get('active', 'off') == 'on')


# --- controller ------------------------------------------------------------
@api_bp.route('/outlier-stage', methods=['GET', 'POST'], endpoint='new_outlier_stage')
@api_bp.route('/outlier-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_outlier_stage')
def outlier_stage_view(stage_index: Optional[int] = None):
    config_path = current_app.config['CONFIG_PATH']

    # Load config (fail fast -> redirect)
    try:
        config = _load_config(config_path)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    is_edit = stage_index is not None

    # Get stage object (existing or default), guard type
    try:
        stage = _stage_for_edit(config, int(stage_index)) if is_edit else default_outlier_stage()
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    if request.method == 'POST':
        _apply_form_to_stage(stage, request.form, is_edit)

        if not is_edit:
            config.setdefault('analyzer_stages', []).append(stage)

        try:
            _validate_and_save_config(config_path, config)
            flash(f"{'Updated' if is_edit else 'New'} outlier stage saved.", 'success')
            return redirect(url_for('ui.index'))
        except ValueError as e:
            flash(f"Error saving config: {e}", 'danger')
            # fall through to re-render

    # Resolve references for rendering
    de_name, deg_name, ds_name = _resolve_outlier_stage_references(config, stage)

    return render_template(
        "stage_form_outlier.html",
        stage=deepcopy(stage),
        edit=is_edit,
        data_element_name=de_name,
        ds_name=ds_name,
        deg_name=deg_name,
    )


