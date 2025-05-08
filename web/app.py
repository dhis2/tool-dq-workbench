import argparse
import os
import subprocess
import sys

import yaml
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from copy import deepcopy
from utils.config_helpers import load_config, save_config
from utils.config_helpers import resolve_uid_name

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))
from core.api_utils import Dhis2ApiUtils

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

def create_app(config_path):
    app = Flask(__name__)
    app.secret_key = 'change-this-key'
    app.config['CONFIG_PATH'] = os.path.abspath(config_path)

    @app.route('/')
    def index():
        with open(app.config['CONFIG_PATH']) as f:
            config = yaml.safe_load(f)
        return render_template("index.html", config=config)

    @app.route('/run', methods=['POST'])
    def run_now():
        result = subprocess.run(
            ['dq-monitor', '--config', app.config['CONFIG_PATH']],
            capture_output=True,
            text=True
        )
        return render_template("run_output.html", output=result.stdout, errors=result.stderr)

    @app.route('/edit-server', methods=['GET', 'POST'])
    def edit_server():
        config_path = app.config['CONFIG_PATH']

        if request.method == 'POST':
            config = load_config(config_path)

            config['server']['base_url'] = request.form['base_url']
            new_token = request.form['d2_token'].strip()
            if new_token:
                config['server']['d2_token'] = new_token
            config['server']['logging_level'] = request.form['logging_level']
            config['server']['max_concurrent_requests'] = int(request.form['max_concurrent_requests'])
            config['server']['max_results'] = int(request.form['max_results'])

            save_config(config_path, config)

            flash('Server configuration updated.', 'success')
            return redirect(url_for('index'))

        #Reload the config
        config = load_config(config_path)

        return render_template("edit_server.html", server=config['server'])

    @app.route('/new-outlier-stage', methods=['GET', 'POST'])
    def new_outlier_stage():
        config_path = app.config['CONFIG_PATH']

        if request.method == 'POST':
            config = load_config(config_path)
            data_element_id = request.form['destination_data_element']
            data_element_name = data_element_id  # fallback if fetch fails

            # Fetch name from DHIS2
            try:
                api_utils = Dhis2ApiUtils(
                    base_url=config['server']['base_url'],
                    d2_token=config['server']['d2_token']
                )
                el = api_utils.fetch_data_element(data_element_id)
                data_element_name = el.get('name', data_element_id)
            except Exception as e:
                flash(f"Warning: Failed to fetch data element name for {data_element_id}", 'warning')

            new_stage = {
                'name': request.form['name'],
                'type': 'outlier',
                'level': int(request.form['level']),
                'duration': request.form['duration'],
                'params': {
                    'dataset': request.form['dataset'],
                    'algorithm': request.form['algorithm'],
                    'threshold': int(request.form['threshold']),
                    'destination_data_element': data_element_id,
                    'destination_data_element_name': data_element_name
                }
            }

            config['stages'].append(new_stage)
            save_config(config_path, config)
            flash('New outlier stage added.', 'success')
            return redirect(url_for('index'))

        return render_template("stage_form_outlier.html", stage=default_outlier_stage(), edit=False)

    @app.route('/new-validation-rule-stage', methods=['GET', 'POST'])
    def new_validation_rule_stage():
        config_path = app.config['CONFIG_PATH']

        if request.method == 'POST':
            config = load_config(config_path)

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
            save_config(config_path, config)
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

    @app.route('/edit-outlier-stage/<int:stage_index>', methods=['GET', 'POST'])
    def edit_outlier_stage(stage_index):
        config_path = app.config['CONFIG_PATH']
        config = load_config(config_path)

        api_utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )

        stage = config['stages'][stage_index]
        de_uid = stage['params'].get('destination_data_element')
        ds_uid = stage['params'].get('dataset')
        de_name = resolve_uid_name(api_utils.fetch_data_element_by_id, de_uid)
        ds_name = resolve_uid_name(api_utils.fetch_dataset_by_id, ds_uid)

        if stage.get('type') != 'outlier':
            flash('Only outlier stages can be edited here.', 'danger')
            return redirect(url_for('index'))

        if request.method == 'POST':
            stage['name'] = request.form['name']
            stage['level'] = int(request.form['level'])
            stage['duration'] = request.form['duration']
            stage['params']['dataset'] = request.form['dataset']
            stage['params']['algorithm'] = request.form['algorithm']
            stage['params']['threshold'] = int(request.form['threshold'])
            stage['params']['destination_data_element'] = request.form['destination_data_element']
            save_config(config_path, config)
            flash(f"Updated outlier stage: {stage['name']}", 'success')
            return redirect(url_for('index'))

        return render_template("stage_form_outlier.html", stage=deepcopy(stage), edit=True, data_element_name=de_name, ds_name = ds_name)


    @app.route('/edit-validation-rule-stage/<int:stage_index>', methods=['GET', 'POST'])
    def edit_validation_rule_stage(stage_index):
        config_path = app.config['CONFIG_PATH']
        config = load_config(config_path)

        api_utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )

        stage = config['stages'][stage_index]
        de_uid = stage['params'].get('destination_data_element')
        data_element_name = resolve_uid_name(api_utils.fetch_data_element_by_id, de_uid)
        vrg_uid = stage['params'].get('validation_rule_groups')
        validation_rule_group_name = resolve_uid_name(api_utils.fetch_validation_rule_group_by_id, vrg_uid)

        if stage.get('type') != 'validation_rules':
            flash('Only validation rule stages can be edited here.', 'danger')
            return redirect(url_for('index'))

        if request.method == 'POST':
            stage['name'] = request.form['name']
            stage['level'] = int(request.form['level'])
            stage['duration'] = request.form['duration']
            stage['params']['validation_rule_groups'] = request.form['validation_rule_groups']
            stage['params']['period_type'] = request.form['period_type']
            stage['params']['destination_data_element'] = request.form['destination_data_element']

            save_config(config_path, config)

            flash(f"Updated validation rule stage: {stage['name']}", 'success')
            return redirect(url_for('index'))

        return render_template(
            "stage_form_validation_rule.html",
            stage=deepcopy(stage),
            edit=True,
            data_element_name=data_element_name,
            validation_rule_group_name=validation_rule_group_name
        )

    @app.route('/delete-stage/<int:stage_index>', methods=['POST'])
    def delete_stage(stage_index):
        config_path = app.config['CONFIG_PATH']
        config = load_config(config_path)

        if 0 <= stage_index < len(config['stages']):
            removed_stage = config['stages'].pop(stage_index)
            save_config(config_path, config)
            flash(f"Deleted stage: {removed_stage['name']}", 'success')
        else:
            flash("Invalid stage index", 'danger')

        return redirect(url_for('index'))

    @app.route('/api/data-elements')
    def api_data_elements():
        config_path = app.config['CONFIG_PATH']
        config = load_config(config_path)
        utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )

        query = request.args.get('q', '').strip()
        try:
            elements = utils.fetch_data_elements(query)
            limited = elements[:20]
            return jsonify([{"id": el["id"], "text": el["name"]} for el in limited])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/datasets')
    def api_datasets():
        config = load_config(app.config['CONFIG_PATH'])
        utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )
        query = request.args.get('q', '').strip()
        try:
            datasets = utils.fetch_data_sets(query)
            #Print the response for debugging
            print(f"Datasets response: {datasets}")
            return jsonify([{"id": ds["id"], "text": ds["name"]} for ds in datasets[:20]])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/validation-rule-groups')
    def api_validation_rule_groups():
        config = load_config(app.config['CONFIG_PATH'])
        utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )
        query = request.args.get('q', '').strip()
        try:
            groups = utils.fetch_validation_rule_groups(query)
            return jsonify([{"id": g["id"], "text": g["name"]} for g in groups[:20]])
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app

def main():
    parser = argparse.ArgumentParser(description="Flask UI for Data Quality Monitor")
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    args = parser.parse_args()

    app = create_app(args.config)
    print(f"Using config: {app.config['CONFIG_PATH']}")
    app.run(debug=True)


if __name__ == '__main__':
    main()
