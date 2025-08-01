import asyncio
import time

import aiohttp
from flask import current_app, jsonify

from app.minmax.min_max_factory import MinMaxFactory
from app.web.routes.api import api_bp
from app.web.utils.config_helpers import load_config


@api_bp.route('/run-minmax-stage/<int:stage_index>', methods=['POST'], endpoint='run_min_max_stage')
def run_min_max_stage(stage_index):
    try:
        start_time = time.time()
        config = load_config(current_app.config['CONFIG_PATH'])
        min_max_factory = MinMaxFactory(config)

        concurrency = config["server"].get("max_concurrent_requests", 5)
        stage = config["min_max_stages"][stage_index]

        async def run():
            semaphore = asyncio.Semaphore(concurrency)
            min_max_factory.semaphore = semaphore
            headers = {
                "Authorization": f"ApiToken {config.get('server', {}).get('d2_token', '')}",
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip"
            }

            async with aiohttp.ClientSession(headers=headers) as session:
                async with semaphore:
                    return await min_max_factory.run_stage(stage, session, semaphore)

        asyncio.run(run())
        result_summary = min_max_factory.result_tracker.get_summary()
        end_time = time.time()
        process_duration = end_time - start_time
        return jsonify({
            "success": True,
            "Value errors": result_summary.get("errors", []),
            "Value fallbacks": result_summary.get("fallbacks", 0),
            "Values ignored": result_summary.get("ignored", 0),
            "Values imported": result_summary.get("imported", 0),
            "Values missing": result_summary.get("missing", 0),
            "Bound warnings": result_summary.get("bound_warnings", 0),
            "Duration": f"{process_duration:.2f} seconds",
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "errors": [str(e)]
        }), 500