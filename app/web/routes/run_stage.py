import asyncio
from copy import deepcopy

from flask import current_app, jsonify

from app.runner import DataQualityMonitor
from app.web.routes.api_blueprint import api_bp
from app.web.utils.config_helpers import load_config


@api_bp.route('/run-stage/<int:stage_index>', methods=['POST'], endpoint='run_stage')
def run_stage(stage_index):
    try:
        full_config = load_config(current_app.config['CONFIG_PATH'])
        stage = full_config['stages'][stage_index]

        # Build minimal config for single stage
        filtered_config = deepcopy(full_config)
        filtered_config['stages'] = [stage]

        monitor = DataQualityMonitor(filtered_config)
        result = asyncio.run(monitor.run_all_stages())
    except Exception as e:
        return jsonify({
            "success": False,
            "output": "",
            "errors": [f"Failed to run stage {stage_index}: {str(e)}"]
        }), 500

    return jsonify({
        "success": True,
        "output": (
            f"Stage '{stage['name']}' executed successfully.<br>"
            f"Duration: {result['duration']}<br>"
            f"Data values posted: {result['data_values_posted']}"
        ),
        "errors": result['errors']
    })
