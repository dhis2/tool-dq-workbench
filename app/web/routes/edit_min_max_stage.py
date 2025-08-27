from copy import deepcopy

from flask import current_app, request, render_template, redirect, url_for, flash

from app.core.config_loader import ConfigManager
from app.core.uid_utils import UidUtils
from app.minmax.min_max_method import MinMaxMethod
from app.web.routes.api import api_bp
from app.web.utils.config_helpers import  save_config

@api_bp.route('/minmax-stage', methods=['GET', 'POST'], endpoint='new_minmax_stage')
@api_bp.route('/minmax-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_minmax_stage')
def minmax_stage_view(stage_index=None):
    config_path = current_app.config['CONFIG_PATH']

    try:
        config = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    is_edit = stage_index is not None

    if is_edit:
        stage = config['min_max_stages'][stage_index]
    else:
        stage = default_minmax_stage()

    if request.method == 'POST':
        # Update stage fields from form
        stage['name'] = request.form['stage_name']
        stage['uid'] = stage.get('uid', UidUtils.generate_uid())
        stage['missing_data_min'] = int(request.form.get('missing_data_min',""))
        stage['missing_data_max'] = int(request.form.get('missing_data_max', ""))
        stage['completeness_threshold'] = float(request.form.get('completeness_threshold', 0.1))
        stage['active'] = request.form.get('active', 'off') == 'on'
        stage['datasets'] = [d.strip() for d in request.form.get('datasets', '').split(',') if d.strip()]
        stage['data_element_groups'] = [d.strip() for d in request.form.get('data_element_groups', '').split(',') if d.strip()]
        stage['data_elements'] = [d.strip() for d in request.form.get('data_elements', '').split(',') if d.strip()]
        stage['org_units'] = [o.strip() for o in request.form.get('org_units', '').split(',') if o.strip()]
        stage['use_dataset_orgunits'] = request.form.get('use_dataset_orgunits', 'off') == 'on'
        stage['org_unit_groups'] = [o.strip() for o in request.form.get('org_unit_groups', '').split(',') if o.strip()]
        stage['groups'] = []

        process_min_max_groups(stage)

        try:
            if not is_edit:
                config.setdefault('min_max_stages', []).append(stage)

            ConfigManager(config_path = None, config=config, validate_structure=True, validate_runtime=False)
            save_config(config_path, config)
            flash(f"{'Updated' if is_edit else 'New'} min/max stage saved.", 'success')
            return redirect(url_for('ui.min_max_index'))

        except Exception as e:
            flash(f"Error saving min/max stage: {str(e)}", 'danger')
            # Fall through to re-render with user input

    return render_template(
        "stage_form_min_max.html",
        stage=deepcopy(stage),
        edit=is_edit,
        minmax_methods=MinMaxMethod.values(),
        minmax_labels=MinMaxMethod.label_map()
    )


def process_min_max_groups(stage):
    # Collect group indices from form keys
    group_indices = sorted({
        int(key.split('-')[1])
        for key in request.form
        if key.startswith('groups-') and key.endswith('-limitMedian')
           and key.split('-')[1].isdigit()
    })

    for i in group_indices:
        method = request.form.get(f'groups-{i}-method')

        group = {
            'limitMedian': float(request.form.get(f'groups-{i}-limitMedian')),
            'method': method,
            'threshold': float(request.form.get(f'groups-{i}-threshold')),
        }

        if method == 'CONSTANT':
            const_min_val = request.form.get(f'groups-{i}-constantMin')
            const_max_val = request.form.get(f'groups-{i}-constantMax')

            if const_min_val not in (None, ''):
                group['constantMin'] = int(float(const_min_val))
            if const_max_val not in (None, ''):
                group['constantMax'] = int(float(const_max_val))

        if all(val not in (None, '') for val in group.values()):
            stage['groups'].append(group)


def default_minmax_stage():
    return {
        'name': '',
        'datasets': [],
        'uid': UidUtils.generate_uid(),
        'completeness_threshold': 0.1,
        'active': True,
        'missing_data_min': 0,
        'missing_data_max': 1000,
        'groups': [{'limitMedian': '20', 'method': 'PREV_MAX', 'threshold': '1.5'},
                   {'limitMedian': '100', 'method': 'MAD', 'threshold': '2'},
                   {'limitMedian': '1000000', 'method': 'BOX_COX', 'threshold': '3'}],
        'org_units': [],
        'org_unit_groups': [],
        'use_dataset_orgunits': False,
        'previous_periods': 12
    }

