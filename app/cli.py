import argparse
import asyncio
import logging
import sys
from datetime import datetime
import os

import aiohttp

from app.analyzers.integrity_analyzer import IntegrityCheckAnalyzer
from app.analyzers.outlier_analyzer import OutlierAnalyzer
from app.analyzers.rule_analyzer import ValidationRuleAnalyzer
from app.core.config_loader import ConfigManager
from app.core.api_utils import Dhis2ApiUtils


class DataQualityMonitor:
    def __init__(self, config):
        self.config = config

        self.base_url = config['server']['base_url']
        self.d2_token = config['server']['d2_token']
        self.max_concurrent_requests = config['server'].get('max_concurrent_requests', 10)
        self.request_headers = {
            'Authorization': f'ApiToken {self.d2_token}',
            'Content-Type': 'application/json'
        }

        # Map stage types to analyzer instances
        self.analyzers = {
            'outlier': OutlierAnalyzer(config, self.base_url, self.request_headers),
            'validation_rules': ValidationRuleAnalyzer(config, self.base_url, self.request_headers),
            'integrity_checks': IntegrityCheckAnalyzer(config, self.base_url, self.request_headers)
        }

        self.api_utils = Dhis2ApiUtils(self.base_url, self.d2_token)

        log_file = config['server'].get("log_file", "dq_monitor.log")
        log_level = config['server'].get("logging_level", "INFO").upper()

        # Ensure log directory exists if a path is provided
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # Force reconfiguration so logs appear even if something configured logging earlier
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ],
            force=True,
        )

    async def run_stage(self, session, stage, semaphore):
        try:
            stage_type = stage.get('type')
            if stage_type not in self.analyzers:
                raise ValueError(f"Unsupported stage type: {stage_type}")

            analyzer = self.analyzers[stage_type]
            logging.info(f"Dispatching stage '{stage['name']}' of type '{stage_type}'")
            return await analyzer.run_stage(stage, session, semaphore)

        except Exception as e:
            logging.error(f"Error running stage '{stage.get('name', '<unnamed>')}': {e}")
            return []

    async def run_all_stages(self):
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        all_data_values = []
        errors = []

        async with aiohttp.ClientSession(headers=self.request_headers) as session:
            logging.info(f"Running all stages with max {self.max_concurrent_requests} concurrent requests")
            clock_start = datetime.now()

            stage_names = [stage['name'] for stage in self.config['analyzer_stages']]
            tasks = [
                self.run_stage(session, stage, semaphore)
                for stage in self.config['analyzer_stages']
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for name, result in zip(stage_names, results):
                if isinstance(result, Exception):
                    logging.error(f"Task failed with exception: {result}")
                    errors.append(f"{name}: {str(result)}")
                elif isinstance(result, dict):
                    all_data_values.extend(result.get("dataValues", []))
                    errors.extend(result.get("errors", []))
                else:
                    msg = f"Unexpected result type from stage '{name}': {type(result)}"
                    logging.warning(msg)
                    errors.append(msg)

            logging.info(f"Posting {len(all_data_values)} data values")
            import_summary = None
            try:
                response = await self.api_utils.create_and_post_data_value_set(all_data_values, session)
                import_summary = Dhis2ApiUtils.parse_import_summary(response)
            except Exception as post_err:
                logging.error(f"Error posting data values: {post_err}")
                errors.append(f"Post failed: {post_err}")

            clock_end = datetime.now()
            logging.info("All stages completed")
            logging.info(f"Process took: {clock_end - clock_start}")

        return {
            "errors": errors,
            "data_values_posted": len(all_data_values),
            "duration": str(clock_end - clock_start),
            "import_summary": import_summary or {}
        }


def run_main():
    parser = argparse.ArgumentParser(description='Run DQ Workbench stages from a configuration file')
    parser.add_argument('--config', required=True, help='Path to configuration file')
    parser.add_argument('--log-level', help='Override logging level (DEBUG, INFO, WARNING, ERROR)')
    parser.add_argument('--log-file', help='Override log file path')
    args = parser.parse_args()

    # Load and validate configuration
    config_manager = ConfigManager(config_path=args.config, config=None, validate_structure=True, validate_runtime=True)
    if not config_manager.config:
        logging.error("Failed to load configuration.")
        sys.exit(1)
    config = config_manager.config

    # Apply CLI overrides for logging without editing the file
    if args.log_level:
        config.setdefault('server', {})['logging_level'] = args.log_level
    if args.log_file:
        config.setdefault('server', {})['log_file'] = args.log_file

    monitor = DataQualityMonitor(config)
    asyncio.run(monitor.run_all_stages())

if __name__ == '__main__':
    run_main()
