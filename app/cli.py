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
        async with aiohttp.ClientSession(headers=self.request_headers) as session:
            logging.info(f"Running all stages with max {self.max_concurrent_requests} concurrent requests")
            clock_start = datetime.now()
            stage_names = [stage['name'] for stage in self.config['analyzer_stages']]
            tasks = [
                self.run_stage(session, stage, semaphore)
                for stage in self.config['analyzer_stages']
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            combined_import_summary, num_upserts, num_deletes, errors = await self._process_tasks(results, session, stage_names)

            clock_end = datetime.now()
            logging.info("All stages completed")
            logging.info(f"Process took: {clock_end - clock_start}")

        return {
            "errors": errors,
            "data_values_posted": num_upserts,
            "data_values_deleted": num_deletes,
            "duration": str(clock_end - clock_start),
            "import_summary": combined_import_summary or {}
        }

    async def _process_tasks(self, results, session, stage_names):
        upserts = []
        deletes = []
        errors = []
        for name, result in zip(stage_names, results):
            if isinstance(result, Exception):
                logging.error(f"Task failed with exception: {result}")
                errors.append(f"{name}: {str(result)}")
            elif isinstance(result, dict):
                upserts.extend(result.get("dataValues", []))
                deletes.extend(result.get("deletions", []))
                errors.extend(result.get("errors", []))
            else:
                msg = f"Unexpected result type from stage '{name}': {type(result)}"
                logging.warning(msg)
                errors.append(msg)
        import_summary = None
        delete_import_summary = None
        if len(upserts) > 0:
            logging.info(f"Posting {len(upserts)} data value upserts")
            try:
                response = await self.api_utils.create_and_post_data_value_set(upserts, session)
                import_summary = Dhis2ApiUtils.parse_import_summary(response)
            except Exception as post_err:
                logging.error(f"Error posting data values: {post_err}")
                errors.append(f"Post failed: {post_err}")
        if len(deletes) > 0:
            logging.info(f"Posting {len(deletes)} data values deletes")
            try:
                params = {'importStrategy': 'DELETE'}
                response = await self.api_utils.create_and_post_data_value_set(deletes, session, params)
                delete_import_summary = Dhis2ApiUtils.parse_import_summary(response)
            except Exception as delete_err:
                logging.error(f"Error deleting data values: {delete_err}")
                errors.append(f"Delete failed: {delete_err}")
        combined_import_summary = self._merge_import_summaries(delete_import_summary, import_summary)
        num_deletes = len(deletes)
        num_upserts = len(upserts)
        return combined_import_summary, num_upserts, num_deletes, errors

    @staticmethod
    def _merge_import_summaries(delete_import_summary, import_summary):
        combined_import_summary = {
            "imported": 0,
            "updated": 0,
            "deleted": 0,
            "ignored": 0,
            "status": "OK"
        }
        if delete_import_summary:
            combined_import_summary["deleted"] += delete_import_summary.get("deleted", 0)
            combined_import_summary["imported"] += delete_import_summary.get("imported", 0)
            combined_import_summary["updated"] += delete_import_summary.get("updated", 0)
            combined_import_summary["ignored"] += delete_import_summary.get("ignored", 0)
            if delete_import_summary.get("status") != "OK":
                combined_import_summary["status"] = delete_import_summary.get("status")
        if import_summary:
            combined_import_summary["imported"] += import_summary.get("imported", 0)
            combined_import_summary["updated"] += import_summary.get("updated", 0)
            combined_import_summary["deleted"] += import_summary.get("deleted", 0)
            combined_import_summary["ignored"] += import_summary.get("ignored", 0)
            if import_summary.get("status") != "OK":
                combined_import_summary["status"] = import_summary.get("status")
        return combined_import_summary


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
