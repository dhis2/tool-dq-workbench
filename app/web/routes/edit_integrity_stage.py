import logging

import requests
from flask import  current_app, request, render_template, redirect, url_for, flash
from copy import deepcopy

from app.core.api_utils import Dhis2ApiUtils
from app.web.utils.config_helpers import load_config, save_config, resolve_uid_name
from app.web.routes.api import api_bp
from app.core.config_loader import ConfigManager

@api_bp.route('/edit-integrity-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_integrity_stage')
def edit_integrity_stage_view(stage_index):
    config_path = current_app.config['CONFIG_PATH']
    try:
        config = load_config(config_path)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    stage = config['stages'][stage_index]

    if stage.get('type') != 'integrity_checks':
        flash('Only the integrity check stage can be edited here.', 'danger')
        return redirect(url_for('ui.index'))

    api_utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )

    deg_uid = stage['params'].get('monitoring_group')

    try:
        deg_name = resolve_uid_name(api_utils.fetch_data_element_group_by_id, deg_uid)
        logging.debug("Fetched data element group name: %s", deg_name)
    except requests.exceptions.RequestException:
        deg_name = deg_uid
        flash(f"Warning: Failed to fetch data element group name for {deg_uid}", 'warning')

    if request.method == 'POST':
        stage['name'] = request.form['stage_name']
        stage['level'] = int(request.form['orgunit_level'])
        stage['duration'] = request.form['duration']
        stage['params']['monitoring_group'] = request.form['monitoring_group']
        stage['params']['period_type'] = request.form['period_type']

        try:
            ConfigManager.validate_structure(config)
            save_config(config_path, config)
            flash(f"Updated integrity stage: {stage['name']}", 'success')
            return redirect(url_for('ui.index'))
        except ValueError as e:
            flash(f"Error saving config: {e}", 'danger')

    return render_template(
        "stage_form_integrity_checks.html",
        stage=deepcopy(stage),
        edit=True,
        deg_name = deg_name
    )