import asyncio
from copy import deepcopy

import aiohttp
from flask import current_app, jsonify

from app.analyzers.integrity_analyzer import IntegrityCheckAnalyzer
from app.core.api_utils import Dhis2ApiUtils
from app.core.config_loader import ConfigManager
from app.cli import DataQualityMonitor
from app.web.routes.api import api_bp


def _load_config(config_path):
    return ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config


def _make_headers(config):
    return {
        'Authorization': f'ApiToken {config["server"]["d2_token"]}',
        'Content-Type': 'application/json',
    }


@api_bp.route('/run-stage/<int:stage_index>', methods=['POST'], endpoint='run_stage')
def run_stage(stage_index):
    try:
        full_config = _load_config(current_app.config['CONFIG_PATH'])
        stage = full_config['analyzer_stages'][stage_index]

        if stage.get('type') == 'integrity_checks':
            # Trigger the DHIS2 async job and return immediately — browser will poll for completion
            headers = _make_headers(full_config)

            async def _trigger():
                analyzer = IntegrityCheckAnalyzer(full_config, full_config['server']['base_url'], headers)
                semaphore = asyncio.Semaphore(full_config['server'].get('max_concurrent_requests', 10))
                async with aiohttp.ClientSession(headers=headers) as session:
                    await analyzer.trigger_only_async(deepcopy(stage), session, semaphore)

            asyncio.run(_trigger())
            return jsonify({
                "success": True,
                "polling": True,
                "stage_index": stage_index,
                "stage_name": stage['name'],
            })

        # Non-integrity stages: run synchronously as before
        filtered_config = deepcopy(full_config)
        filtered_config['analyzer_stages'] = [stage]

        monitor = DataQualityMonitor(filtered_config)
        result = asyncio.run(monitor.run_all_stages())

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


@api_bp.route('/integrity-running', methods=['GET'], endpoint='integrity_running')
def integrity_running():
    """Check whether a DHIS2 dataIntegrity summary job is still running."""
    try:
        config = _load_config(current_app.config['CONFIG_PATH'])
        headers = _make_headers(config)
        base_url = config['server']['base_url']

        async def _check():
            url = f'{base_url}/api/dataIntegrity/summary/running'
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    return None

        running = asyncio.run(_check())
        return jsonify({"running": bool(running)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/collect-integrity/<int:stage_index>', methods=['POST'], endpoint='collect_integrity')
def collect_integrity(stage_index):
    """Fetch completed integrity results and post them to DHIS2."""
    try:
        full_config = _load_config(current_app.config['CONFIG_PATH'])
        stage = full_config['analyzer_stages'][stage_index]
        headers = _make_headers(full_config)

        async def _collect():
            analyzer = IntegrityCheckAnalyzer(full_config, full_config['server']['base_url'], headers)
            api_utils = Dhis2ApiUtils(full_config['server']['base_url'], full_config['server']['d2_token'])
            semaphore = asyncio.Semaphore(full_config['server'].get('max_concurrent_requests', 10))
            async with aiohttp.ClientSession(headers=headers) as session:
                data_value_set = await analyzer.collect_results_async(deepcopy(stage), session, semaphore)
                return await api_utils.post_data_value_set(data_value_set, session)

        import_response = asyncio.run(_collect())
        summary = Dhis2ApiUtils.parse_import_summary(import_response)

        summary_text = ""
        if summary.get("status") == "OK":
            summary_text = (
                f"<br>Imported: {summary.get('imported', 0)}, "
                f"Updated: {summary.get('updated', 0)}, "
                f"Ignored: {summary.get('ignored', 0)}, "
                f"Deleted: {summary.get('deleted', 0)}"
            )

        return jsonify({
            "success": True,
            "output": (
                f"Integrity stage '{stage['name']}' completed."
                f"{summary_text}"
            ),
            "errors": []
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "output": "",
            "errors": [f"Failed to collect integrity results: {str(e)}"]
        }), 500
