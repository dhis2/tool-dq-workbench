import logging
from copy import deepcopy
import requests
from flask import current_app, request, render_template, redirect, url_for, flash

from app.core.api_utils import Dhis2ApiUtils
from app.core.config_loader import ConfigManager
from app.core.uid_utils import UidUtils
from app.web.routes.api import api_bp
from app.web.utils.config_helpers import load_config, save_config


def default_outlier_stage():
    return {
        'name': '',
        'type': 'outlier',
        'level': 1,
        'duration': '12 months',
        'params': {
            'dataset': '',
            'algorithm': 'MOD_Z_SCORE',
            'threshold': 3,
            'destination_data_element': ''
        }
    }


@api_bp.route('/outlier-stage', methods=['GET', 'POST'], endpoint='new_outlier_stage')
@api_bp.route('/outlier-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_outlier_stage')
def outlier_stage_view(stage_index=None):
    config_path = current_app.config['CONFIG_PATH']
    try:
        config = load_config(config_path)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    is_edit = stage_index is not None

    # If edit, load existing stage
    if is_edit:
        stage = config['analyzer_stages'][stage_index]
        if stage.get('type') != 'outlier':
            flash('Only outlier stages can be edited here.', 'danger')
            return redirect(url_for('ui.index'))
    else:
        stage = default_outlier_stage()

    api_utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )

    # Fetch data element and dataset names
    de_uid = stage['params'].get('destination_data_element')
    ds_uid = stage['params'].get('dataset')

    def resolve_name(fetch_func, uid):
        if not uid:
            return ''
        try:
            result = fetch_func(uid)
            return result.get('name') or uid
        except requests.exceptions.RequestException:
            flash(f"Warning: Failed to fetch name for {uid}", 'warning')
            return uid

    de_name = resolve_name(api_utils.fetch_data_element_by_id, de_uid)
    ds_name = resolve_name(api_utils.fetch_dataset_by_id, ds_uid)

    # Handle form submission
    if request.method == 'POST':
        stage['name'] = request.form['stage_name']
        stage['level'] = int(request.form['orgunit_level'])
        stage['duration'] = request.form['duration']
        stage['params']['dataset'] = request.form['dataset']
        stage['params']['algorithm'] = request.form['algorithm']
        stage['params']['threshold'] = int(request.form['threshold'])
        stage['params']['destination_data_element'] = request.form['destination_data_element']

        # Handle UID generation/validation
        if not is_edit or not stage.get('uid'):
            stage['uid'] = UidUtils.generate_uid()

        # Handle active status (only relevant for editing)
        if is_edit:
            logging.debug("Stage active status: %s", request.form.get('active', 'off'))
            stage['active'] = request.form.get('active', 'off') == 'on'

        if not is_edit:
            config.setdefault('analyzer_stages', []).append(stage)

        try:
            ConfigManager.validate_structure(config)
            save_config(config_path, config)
            flash(f"{'Updated' if is_edit else 'New'} outlier stage saved.", 'success')
            return redirect(url_for('ui.index'))
        except ValueError as e:
            flash(f"Error saving config: {e}", 'danger')
            # Fall through to re-render the form

    return render_template(
        "stage_form_outlier.html",
        stage=deepcopy(stage),
        edit=is_edit,
        data_element_name=de_name,
        ds_name=ds_name
    )
