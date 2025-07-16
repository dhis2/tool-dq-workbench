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
    if request.method == 'POST':
        stage['name'] = request.form['stage_name']
        stage['completeness_threshold'] = request.form['completeness_threshold']
        stage['previous_periods'] = int(request.form['previous_periods'])
        stage['datasets'] = [d.strip() for d in request.form.get('datasets', '').split(',') if d.strip()]
        stage['org_units'] = [o.strip() for o in request.form.get('orgunits', '').split(',') if o.strip()]
        stage['groups'] = []
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
                'limitMedian': request.form.get(f'groups-{i}-limitMedian'),
                'method': request.form.get(f'groups-{i}-method'),
                'threshold': request.form.get(f'groups-{i}-threshold')
            }
            if group['limitMedian'] and group['method'] and group['threshold']:
                stage['groups'].append(group)

        try:
            ConfigManager.validate_structure(config)
            save_config(config_path, config)
            flash(f"Updated min/max stage: {stage['name']}", 'success')
            return redirect(url_for('ui.index'))
        except ValueError as e:
            flash(f"Error saving config: {e}", 'danger')

    return render_template(
        "stage_form_min_max.html",
        stage=deepcopy(stage),
        edit=True
    )