from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash

from app.web.routes.api_blueprint import api_bp
from app.web.utils.config_helpers import load_config, save_config


@api_bp.route('/new-validation-rule-stage', methods=['GET', 'POST'], endpoint='new_validation_rule_stage')
def new_validation_rule_stage_view():
    server_config_path = current_app.config['CONFIG_PATH']

    if request.method == 'POST':
        config = load_config(server_config_path)

        new_stage = {
            'name': request.form['name'],
            'type': 'validation_rules',
            'level': int(request.form['level']),
            'duration': request.form['duration'],
            'params': {
                'validation_rule_groups': request.form['validation_rule_groups'],
                'period_type': request.form['period_type'],
                'destination_data_element': request.form['destination_data_element']
            }
        }

        config['stages'].append(new_stage)
        save_config(server_config_path, config)
        flash('New validation rule stage added.', 'success')
        return redirect(url_for('index'))

    blank_stage = {
        'name': '',
        'type': 'validation_rules',
        'level': 1,
        'duration': '12 months',
        'params': {
            'validation_rule_groups': '',
            'period_type': '',
            'destination_data_element': ''
        }
    }

    return render_template("stage_form_validation_rule.html", stage=blank_stage, edit=False)
