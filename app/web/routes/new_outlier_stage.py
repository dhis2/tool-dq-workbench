import requests
from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash

from app.core.api_utils import Dhis2ApiUtils
from app.web.utils.config_helpers import load_config, save_config, resolve_uid_name
from app.web.routes.api import api_bp
# Utility to generate a blank outlier stage
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

@api_bp.route('/new_outlier_stage', methods=['GET', 'POST'], endpoint = 'new_outlier_stage')
def new_outlier_stage_view():
    server_config_path = current_app.config['CONFIG_PATH']


    if request.method == 'POST':
        config = load_config(server_config_path)
        if 'stages' not in config:
            config['stages'] = []

        data_element_id = request.form['destination_data_element']
        data_element_name = data_element_id
        api_utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )

        try:
            el = api_utils.fetch_data_element_by_id(data_element_id)
            data_element_name = el.get('name', data_element_id)
        except requests.exceptions.RequestException:
            flash(f"Warning: Failed to fetch data element name for {data_element_id}", 'warning')

        new_stage = {
            'name': request.form['stage_name'],
            'type': 'outlier',
            'level': int(request.form['orgunit_level']),
            'duration': request.form['duration'],
            'params': {
                'dataset': request.form['dataset'],
                'algorithm': request.form['algorithm'],
                'threshold': int(request.form['threshold']),
                'destination_data_element': data_element_id,
                'destination_data_element_name': data_element_name
            }
        }

        try:
            config['stages'].append(new_stage)
            save_config(server_config_path, config)
            flash('New outlier stage added.', 'success')
            return redirect(url_for('ui.index'))
        except ValueError as e:
            flash(f"Failed to save stage: {e}", 'danger')

            # Resolve names so TomSelect gets friendly values
            try:
                de_name = resolve_uid_name(api_utils.fetch_data_element_by_id,
                                           new_stage['params'].get('destination_data_element'))
            except requests.exceptions.RequestException:
                de_name = new_stage['params'].get('destination_data_element', '')
            try:
                ds_name = resolve_uid_name(api_utils.fetch_dataset_by_id, new_stage['params'].get('dataset'))
            except requests.exceptions.RequestException:
                ds_name = new_stage['params'].get('dataset', '')

            return render_template(
                "stage_form_outlier.html",
                stage=new_stage,
                edit=False,
                data_element_name=de_name,
                ds_name=ds_name
            )

    return render_template("stage_form_outlier.html", stage=default_outlier_stage(), edit=False)
