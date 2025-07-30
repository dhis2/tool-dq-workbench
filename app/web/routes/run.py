import asyncio

from flask import Blueprint, current_app, render_template, flash, jsonify, redirect, url_for

from app.runner import DataQualityMonitor
from app.web.utils.config_helpers import load_config

from app.web.routes.api import api_bp

@api_bp.route('/run', methods=['POST'], endpoint='run')
def run_now():
    try:
        config = load_config(current_app.config['CONFIG_PATH'])

        # Only keep active stages
        active_stages = [
            stage for stage in config.get("analyzer_stages", [])
            if stage.get("active", False)  # Explicitly default to False
        ]

        if not active_stages:
            flash("No active stages to run.", "warning")
            return redirect(url_for('ui.index'))

        # Replace only the active stages in a shallow copy of config
        config_filtered = {**config, "analyzer_stages": active_stages}

        monitor = DataQualityMonitor(config_filtered)
        result = asyncio.run(monitor.run_all_stages())

        # Build summary text from import summary
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
                f"All stages executed successfully.<br>"
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
            "errors": [str(e)]
        }), 500
