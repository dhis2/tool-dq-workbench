from flask import Blueprint, current_app, request, jsonify
from app.web.utils.config_helpers import load_config
from app.core.api_utils import Dhis2ApiUtils

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/data-elements')
def api_data_elements():
    config = load_config(current_app.config['CONFIG_PATH'])
    utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )
    query = request.args.get('q', '').strip()
    try:
        elements = utils.fetch_data_elements(query)
        return jsonify([{"id": el["id"], "text": el["name"]} for el in elements[:20]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/datasets')
def api_datasets():
    config = load_config(current_app.config['CONFIG_PATH'])
    utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )
    query = request.args.get('q', '').strip()
    try:
        datasets = utils.fetch_data_sets(query)
        print(f"Datasets response: {datasets}")
        return jsonify([{"id": ds["id"], "text": ds["name"]} for ds in datasets[:20]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/validation-rule-groups')
def api_validation_rule_groups():
    config = load_config(current_app.config['CONFIG_PATH'])
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

@api_bp.route('/data-element-groups')
def api_data_element_groups():
    config = load_config(current_app.config['CONFIG_PATH'])
    utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )
    query = request.args.get('q', '').strip()
    try:
        groups = utils.fetch_data_element_groups(query)
        return jsonify([{"id": g["id"], "text": g["name"]} for g in groups[:20]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500