import asyncio
import time
from io import StringIO

import aiohttp
from flask import current_app, jsonify, Response

from app.core.config_loader import ConfigManager
from app.minmax.min_max_factory import MinMaxFactory
from app.web.routes.api import api_bp


@api_bp.route('/minmax-analysis/<int:stage_index>', methods=['POST'], endpoint='minmax_analysis')
def analyze_min_max_stage(stage_index):
    try:
        start_time = time.time()
        config_path = current_app.config.get('CONFIG_PATH')
        config = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config
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
                    return await min_max_factory.analyze_stage(stage, session, semaphore)

        df = asyncio.run(run())
        buf = StringIO()
        df.to_csv(buf, index=False)
        csv_bytes = buf.getvalue()
        return Response(
            csv_bytes,
            mimetype='text/csv',
            headers={
                "Content-Disposition": f'attachment; filename=minmax_stage_{stage_index}.csv'
            }
        )

    except Exception as e:
        return jsonify({
            "success": False,
            "errors": [str(e)]
        }), 500