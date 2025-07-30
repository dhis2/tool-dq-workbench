import requests
from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash

from app.core.api_utils import Dhis2ApiUtils
from app.core.config_loader import ConfigManager
from app.web.routes.edit_min_max_stage import default_minmax_stage
from app.web.utils.config_helpers import load_config, save_config
from app.web.routes.api import api_bp


@api_bp.route('/new_minmax_stage', methods=['GET', 'POST'], endpoint = 'new_minmax_stage')
def new_minmax_stage_view():
    server_config_path = current_app.config['CONFIG_PATH']

    if request.method == 'POST':
        config = load_config(server_config_path)
        if 'min_max_stages' not in config:
            config['min_max_stages'] = []

        new_stage = default_minmax_stage()
        new_stage['name'] = request.form['stage_name']
        new_stage['completeness_threshold'] = request.form['completeness_threshold']
        new_stage['previous_periods'] = int(request.form['previous_periods'])
        new_stage['datasets'] = [d.strip() for d in request.form.get('datasets', '').split(',') if d.strip()]
        new_stage['org_units'] = [o.strip() for o in request.form.get('org_units', '').split(',') if o.strip()]
        new_stage['groups'] = []
        group_indices = []
        for key in request.form.keys():
            if key.startswith('groups-') and key.endswith('-limitMedian'):
                try:
                    idx = int(key.split('-')[1])
                    group_indices.append(idx)
                except ValueError:
                    continue
        group_indices = sorted(set(group_indices))
        for i in group_indices:
            group = {
                'limitMedian': float(request.form.get(f'groups-{i}-limitMedian')),
                'method': request.form.get(f'groups-{i}-method'),
                'threshold': float(request.form.get(f'groups-{i}-threshold')),
            }
            if group['limitMedian'] and group['method'] and group['threshold']:
                new_stage['groups'].append(group)
        try:
            config['min_max_stages'].append(new_stage)
            ConfigManager.validate_structure(config)
            save_config(server_config_path, config)
            flash('New minmax stage added.', 'success')
            return redirect(url_for('ui.min_max_index'))
        except Exception as e:
            flash(f"Error adding new minmax stage: {str(e)}", 'danger')
            return render_template("stage_form_min_max.html", stage=new_stage, edit=False)

    return render_template("stage_form_min_max.html", stage=default_minmax_stage(), edit=False)