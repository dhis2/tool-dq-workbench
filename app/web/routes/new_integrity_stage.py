import requests
from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash

from app.core.api_utils import Dhis2ApiUtils
from app.core.config_loader import ConfigManager
from app.web.utils.config_helpers import load_config, save_config, resolve_uid_name
from app.web.routes.api import api_bp
# Utility to generate a blank outlier stage
def default_integrity_stage():
    return {
        'name': '',
        'type': 'integrity_checks',
        'level': 1,
        'duration': '12 months',
        'params': {
            'monitoring_group': '',
            'period_type': 'Monthly'
        }
    }

@api_bp.route('/new_integrity_stage', methods=['GET', 'POST'], endpoint = 'new_integrity_stage')
def new_integrity_stage_view():
    server_config_path = current_app.config['CONFIG_PATH']

    if request.method == 'POST':
        config = load_config(server_config_path)
        if 'stages' not in config:
            config['stages'] = []

        deg_uid = request.form['monitoring_group']
        deg_name = deg_uid
        api_utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )

        try:
            el = api_utils.fetch_data_element_group_by_id(deg_uid)
            deg_name = el.get('name', deg_uid)
        except requests.exceptions.RequestException:
            flash(f"Warning: Failed to fetch data element name for {deg_uid}", 'warning')

        new_stage = {
            'name': request.form['stage_name'],
            'type': 'integrity_checks',
            'level': int(request.form['orgunit_level']),
            'duration': request.form['duration'],
            'params': {
                'monitoring_group': request.form['monitoring_group'],
                'period_type': request.form['period_type'],
                'dataelement_group_name': deg_name
            }
        }

        try:
            config['stages'].append(new_stage)
            ConfigManager.validate_structure(config)
            save_config(server_config_path, config)
            flash('New integrity stage added.', 'success')
            return redirect(url_for('ui.index'))
        except ValueError as e:
            flash(f"Failed to save stage: {e}", 'danger')

            return render_template(
                "stage_form_outlier.html",
                stage=new_stage,
                edit=False,
                deg_name=deg_name
            )

    return render_template("stage_form_outlier.html", stage=default_integrity_stage(), edit=False)
