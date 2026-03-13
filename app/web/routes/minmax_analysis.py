import asyncio
import threading
import time
import uuid
from io import StringIO

import aiohttp
from flask import current_app, jsonify, Response

from app.core.config_loader import ConfigManager
from app.minmax.min_max_factory import MinMaxFactory
from app.web.routes.api import api_bp

# In-memory job store: job_id -> {"status": "running"|"done"|"error", "csv": str, "message": str}
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _run_analysis_in_background(job_id: str, config: dict, stage: dict):
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
            return await factory.analyze_stage(stage, session, semaphore)

    try:
        df = asyncio.run(run())
        if df is None or df.empty:
            with _jobs_lock:
                _jobs[job_id] = {"status": "error", "message": "No data returned from analysis."}
            return
        buf = StringIO()
        df.to_csv(buf, index=False)
        with _jobs_lock:
            _jobs[job_id] = {"status": "done", "csv": buf.getvalue()}
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id] = {"status": "error", "message": str(e)}


@api_bp.route('/minmax-analysis/<int:stage_index>', methods=['POST'], endpoint='minmax_analysis')
def analyze_min_max_stage(stage_index):
    try:
        config_path = current_app.config.get('CONFIG_PATH')
        config = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config
        stage = config["min_max_stages"][stage_index]

        job_id = str(uuid.uuid4())
        with _jobs_lock:
            _jobs[job_id] = {"status": "running"}

        t = threading.Thread(target=_run_analysis_in_background, args=(job_id, config, stage), daemon=True)
        t.start()

        return jsonify({"polling": True, "job_id": job_id})

    except Exception as e:
        return jsonify({"success": False, "errors": [str(e)]}), 500


@api_bp.route('/minmax-analysis-status/<job_id>', methods=['GET'], endpoint='minmax_analysis_status')
def minmax_analysis_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"status": "not_found"}), 404
    if job["status"] == "error":
        return jsonify({"status": "error", "message": job["message"]})
    return jsonify({"status": job["status"]})


@api_bp.route('/minmax-analysis-result/<job_id>', methods=['GET'], endpoint='minmax_analysis_result')
def minmax_analysis_result(job_id):
    with _jobs_lock:
        job = _jobs.pop(job_id, None)
    if job is None or job.get("status") != "done":
        return jsonify({"error": "Result not available"}), 404
    return Response(
        job["csv"],
        mimetype='text/csv',
        headers={"Content-Disposition": f'attachment; filename=minmax_analysis_{job_id[:8]}.csv'}
    )
