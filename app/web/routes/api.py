import logging

from flask import Blueprint, current_app, request, jsonify
from app.core.api_utils import Dhis2ApiUtils
from app.core.config_loader import ConfigManager

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/data-elements')
def api_data_elements():
    import traceback

    config = ConfigManager(current_app.config['CONFIG_PATH'])
    utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )
    query = request.args.get('q', '').strip()

    logging.info(f"Searching data elements with query: '{query}'")

    try:
        if query:
            filters = [f'name:ilike:{query}']
            elements = utils.fetch_data_elements(filters=filters)
        else:
            # No query, return empty list or first 20 elements
            elements = utils.fetch_metadata_list('dataElements', 'dataElements')

        logging.info(f"Found {len(elements)} elements")

        # Debug: Log the first element structure to see what we're working with
        if elements:
            logging.debug(f"First element structure: {elements[0]}")

        result = [{"id": el["id"], "text": el["name"]} for el in elements[:20]]
        logging.info(f"Returning {len(result)} formatted elements")

        return jsonify(result)

    except Exception as e:
        logging.error(f"Error in api_data_elements: {str(e)}")
        logging.error(f"Full traceback: {traceback.format_exc()}")
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
        filters = [f"name:ilike:{query}"] if query else []
        datasets = utils.fetch_data_sets(filters=filters)
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
        # Apply proper filter format if a search query is present
        filters = [f"name:ilike:{query}"] if query else []

        groups = utils.fetch_validation_rule_groups(filters=filters)
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
        filters = [f"name:ilike:{query}"] if query else []
        groups = utils.fetch_data_element_groups(filters=filters)
        return jsonify([{"id": g["id"], "text": g["name"]} for g in groups[:20]])
    except Exception as e:
        return jsonify({"error": str(e)}), 500