# run_get_data_values.py

import asyncio
import aiohttp
import yaml
import logging
from app.generators.min_max_factory import MinMaxGenerator  # Adjust path if needed

logging.basicConfig(level=logging.DEBUG)

async def main():
    # Load config
    with open("../config/gh_sandbox_full.yaml", "r") as f:
        config = yaml.safe_load(f)

    stage = config["min_max_stages"][0]
    headers = {
        "Authorization": f"ApiToken {config['server']['d2_token']}"
    }

    # Create generator
    generator = MinMaxGenerator(config, config["server"]["base_url"], headers)

    # Set up aiohttp client session and semaphore
    concurrency = config["server"].get("max_concurrent_requests", 5)
    semaphore = asyncio.Semaphore(concurrency)

    async with aiohttp.ClientSession() as session:
        data_values = await generator.get_data_values(stage, session, semaphore)

        print("\n=== DATA VALUES FETCHED ===")
        for val in data_values[:5]:  # Show just a few
            print(val)
        print(f"\nTotal fetched: {len(data_values)}")

if __name__ == "__main__":
    asyncio.run(main())
