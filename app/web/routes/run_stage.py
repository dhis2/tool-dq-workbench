import asyncio
from copy import deepcopy

from flask import current_app, jsonify

from app.core.config_loader import ConfigManager
from app.cli import DataQualityMonitor
from app.web.routes.api import api_bp


@api_bp.route('/run-stage/<int:stage_index>', methods=['POST'], endpoint='run_stage')
def run_stage(stage_index):
    try:
        full_config = ConfigManager(current_app.config['CONFIG_PATH'], config = None, validate_structure=True, validate_runtime=False).config
        stage = full_config['analyzer_stages'][stage_index]

        # Build minimal config for single stage
        filtered_config = deepcopy(full_config)
        filtered_config['analyzer_stages'] = [stage]

        monitor = DataQualityMonitor(filtered_config)
        result = asyncio.run(monitor.run_all_stages())

        # Extract import summary details
        import_summary = result.get("import_summary", {})
        summary_text = ""
        if import_summary.get("status") == "OK":
            summary_text = (
                f"<br>Imported: {import_summary.get('imported', 0)}, "
                f"Updated: {import_summary.get('updated', 0)}, "
                f"Ignored: {import_summary.get('ignored', 0)}, "
                f"Deleted: {import_summary.get('deleted', 0)}"
            )
        elif import_summary:
            summary_text = f"<br><strong>Server status:</strong> {import_summary.get('status')}"

        return jsonify({
            "success": True,
            "output": (
                f"Stage '{stage['name']}' executed successfully.<br>"
                f"Duration: {result['duration']}<br>"
                f"Data values posted: {result['data_values_posted']}"
                f"{summary_text}"
            ),
            "errors": result['errors']
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "output": "",
            "errors": [f"Failed to run stage {stage_index}: {str(e)}"]
        }), 500
