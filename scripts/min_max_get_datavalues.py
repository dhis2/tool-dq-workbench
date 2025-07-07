# scripts/min_max_get_datavalues.py

import os
import sys
import asyncio
import time

import aiohttp
import logging
from app.core.config_loader import ConfigManager
from app.generators.min_max_factory import MinMaxGenerator
import pprint

# Set up project root path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_PATH = os.path.join(BASE_DIR, 'config', 'gh_sandbox_full.yml')

logging.basicConfig(level=logging.DEBUG)

async def main():

    # Load and validate config
    config_loader = ConfigManager(CONFIG_PATH)
    config = config_loader.config
    generator = MinMaxGenerator(config)

    # Get first min_max stage from config
    stage = config["min_max_stages"][0]
    logging.info(f"Using stage: {stage['name']}")


    # Set up aiohttp session and semaphore
    concurrency = config["server"].get("max_concurrent_requests", 5)
    semaphore = asyncio.Semaphore(concurrency)
    headers = {
        "Authorization": f"ApiToken {config.get('server', {}).get('d2_token', '')}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip"
    }
    async with aiohttp.ClientSession(headers=headers) as session:

        resp = await generator.run_stage(stage, session, semaphore)
        logging.info("Stage completed successfully")
        logging.debug("Response from run_stage: %s", pprint.pformat(resp))
if __name__ == "__main__":
    start = time.perf_counter()
    asyncio.run(main())
    end = time.perf_counter()
    logging.info(f"Script completed in {end - start:.2f} seconds")
