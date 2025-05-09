import asyncio

from flask import Blueprint, current_app, render_template, flash, jsonify

from app.runner import DataQualityMonitor
from app.web.utils.config_helpers import load_config

from app.web.routes.api_blueprint import api_bp

@api_bp.route('/run', methods=['POST'], endpoint='run')
def run_now():
    try:
        config = load_config(current_app.config['CONFIG_PATH'])
        monitor = DataQualityMonitor(config)
        result = asyncio.run(monitor.run_all_stages())
        return jsonify({
            "success": True,
            "output": (
                f"All stages executed successfully.<br>"
                f"Duration: {result['duration']}<br>"
                f"Data values posted: {result['data_values_posted']}"
            ),
            "errors": result['errors']
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "output": "",
            "errors": [str(e)]
        }), 500
