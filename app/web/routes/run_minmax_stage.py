import asyncio
import threading
import time
import uuid

import aiohttp
from flask import current_app, jsonify

from app.core.config_loader import ConfigManager
from app.minmax.min_max_factory import MinMaxFactory
from app.web.routes.api import api_bp

_jobs: dict = {}
_jobs_lock = threading.Lock()


def _run_stage_in_background(job_id: str, config: dict, stage: dict):
    async def run():
        concurrency = config["server"].get("max_concurrent_requests", 5)
        semaphore = asyncio.Semaphore(concurrency)
        headers = {
            "Authorization": f"ApiToken {config.get('server', {}).get('d2_token', '')}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip"
        }
        factory = MinMaxFactory(config)
        async with aiohttp.ClientSession(headers=headers) as session:
            await factory.run_stage(stage, session, semaphore)
        return factory.result_tracker.get_summary()

    start_time = time.time()
    try:
        summary = asyncio.run(run())
        duration = time.time() - start_time
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "done",
                "summary": summary,
                "duration": duration,
            }
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id] = {"status": "error", "message": str(e)}


@api_bp.route('/run-minmax-stage/<int:stage_index>', methods=['POST'], endpoint='run_min_max_stage')
def run_min_max_stage(stage_index):
    try:
        config_path = current_app.config.get('CONFIG_PATH')
        config = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config
        stage = config["min_max_stages"][stage_index]

        job_id = str(uuid.uuid4())
        with _jobs_lock:
            _jobs[job_id] = {"status": "running"}

        t = threading.Thread(target=_run_stage_in_background, args=(job_id, config, stage), daemon=True)
        t.start()

        return jsonify({"polling": True, "job_id": job_id})

    except Exception as e:
        return jsonify({"success": False, "errors": [str(e)]}), 500


@api_bp.route('/run-minmax-stage-status/<job_id>', methods=['GET'], endpoint='run_minmax_stage_status')
def run_minmax_stage_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"status": "not_found"}), 404
    if job["status"] == "error":
        return jsonify({"status": "error", "message": job["message"]})
    if job["status"] == "done":
        result = _jobs.pop(job_id)
        summary = result["summary"]
        duration = result["duration"]
        return jsonify({
            "status": "done",
            "success": True,
            "Value errors": summary.get("errors", []),
            "Value fallbacks": summary.get("fallbacks", 0),
            "Values ignored": summary.get("ignored", 0),
            "Values imported": summary.get("imported", 0),
            "Values missing": summary.get("missing", 0),
            "Bound warnings": summary.get("bound_warnings", 0),
            "Duration": f"{duration:.2f} seconds",
            "Values imputed": summary.get("imputed", 0),
        })
    return jsonify({"status": "running"})
