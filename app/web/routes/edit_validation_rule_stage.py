from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash
from copy import deepcopy
import requests

from app.core.api_utils import Dhis2ApiUtils
from app.web.utils.config_helpers import load_config, save_config, resolve_uid_name
from app.web.routes.api_blueprint import api_bp

@api_bp.route('/edit-validation-rule-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_validation_rule_stage')
def edit_validation_rule_stage_view(stage_index):
    config_path = current_app.config['CONFIG_PATH']
    config = load_config(config_path)

    stage = config['stages'][stage_index]

    if stage.get('type') != 'validation_rules':
        flash('Only validation rule stages can be edited here.', 'danger')
        return redirect(url_for('index.index'))

    api_utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )

    de_uid = stage['params'].get('destination_data_element')
    vrg_uid = stage['params'].get('validation_rule_groups')

    try:
        data_element_name = resolve_uid_name(api_utils.fetch_data_element_by_id, de_uid)
    except requests.exceptions.RequestException:
        data_element_name = de_uid
        flash(f"Warning: Failed to fetch data element name for {de_uid}", 'warning')

    try:
        validation_rule_group_name = resolve_uid_name(api_utils.fetch_validation_rule_group_by_id, vrg_uid)
    except requests.exceptions.RequestException:
        validation_rule_group_name = vrg_uid
        flash(f"Warning: Failed to fetch validation rule group name for {vrg_uid}", 'warning')

    if request.method == 'POST':
        stage['name'] = request.form['name']
        stage['level'] = int(request.form['level'])
        stage['duration'] = request.form['duration']
        stage['params']['validation_rule_groups'] = request.form['validation_rule_groups']
        stage['params']['period_type'] = request.form['period_type']
        stage['params']['destination_data_element'] = request.form['destination_data_element']

        save_config(config_path, config)
        flash(f"Updated validation rule stage: {stage['name']}", 'success')
        return redirect(url_for('index.index'))

    return render_template(
        "stage_form_validation_rule.html",
        stage=deepcopy(stage),
        edit=True,
        data_element_name=data_element_name,
        validation_rule_group_name=validation_rule_group_name
    )
