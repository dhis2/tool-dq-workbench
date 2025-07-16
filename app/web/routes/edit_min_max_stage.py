from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash
from copy import deepcopy
import requests

from app.core.api_utils import Dhis2ApiUtils
from app.web.utils.config_helpers import load_config, save_config, resolve_uid_name
from app.web.routes.api import api_bp
from app.core.config_loader import ConfigManager

@api_bp.route('/edit-minmax-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_minmax_stage')

def edit_minmax_stage_view(stage_index):
    config_path = current_app.config['CONFIG_PATH']
    try:
        config = load_config(config_path)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    stage = config['min_max_stages'][stage_index]

    api_utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )

    de_uid = stage['params'].get('destination_data_element')
    ds_uid = stage['params'].get('dataset')

    try:
        de_name = resolve_uid_name(api_utils.fetch_data_element_by_id, de_uid)
    except requests.exceptions.RequestException:
        de_name = de_uid
        flash(f"Warning: Failed to fetch data element name for {de_uid}", 'warning')

    try:
        ds_name = resolve_uid_name(api_utils.fetch_dataset_by_id, ds_uid)
    except requests.exceptions.RequestException:
        ds_name = ds_uid
        flash(f"Warning: Failed to fetch dataset name for {ds_uid}", 'warning')

    if request.method == 'POST':
        stage['name'] = request.form['stage_name']
        stage['level'] = int(request.form['orgunit_level'])
        stage['duration'] = request.form['duration']
        stage['params']['dataset'] = request.form['dataset']
        stage['params']['algorithm'] = request.form['algorithm']
        stage['params']['threshold'] = int(request.form['threshold'])
        stage['params']['destination_data_element'] = request.form['destination_data_element']

        try:
            ConfigManager.validate_structure(config)
            save_config(config_path, config)
            flash(f"Updated min/max stage: {stage['name']}", 'success')
            return redirect(url_for('ui.index'))
        except ValueError as e:
            flash(f"Error saving config: {e}", 'danger')

    return render_template(
        "stage_form_minmax_generation.html",
        stage=deepcopy(stage),
        data_element_name=de_name,
        dataset_name=ds_name
    )