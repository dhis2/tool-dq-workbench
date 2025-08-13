import yaml

from app.core.api_utils import Dhis2ApiUtils
import re
from app.core.time_unit import TimeUnit
import logging
from typing import Any, Dict
from build.lib.app.core.period_utils import Dhis2PeriodUtils


class ConfigManager:
    def __init__(self, config_path, config, validate_structure=True, validate_runtime=True):
        if config_path:
            with open(config_path, 'r') as stream:
                config = yaml.safe_load(stream)

        if config is None or not isinstance(config, dict):
            raise ValueError("Config must be provided and be a dictionary after loading.")

        self.config: Dict[str, Any] = config

        server = self.config.get('server')
        if not isinstance(server, dict):
            raise ValueError("Missing or invalid 'server' section in config.")
        self.server: Dict[str, Any] = server

        if validate_structure:
            self.validate_structure(self.config)
        if validate_runtime:
            self._validate_runtime(self.config)

    @classmethod
    def _validate_runtime(cls, config):
        # Check base_url format
        url = config['server'].get('base_url', '')
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid base URL: '{url}'. Must start with http:// or https://")
        if url.endswith('/'):
            raise ValueError("Base URL should not end with a slash")

        # Attempt to ping the server
        api_utils = Dhis2ApiUtils(url, config['server'].get('d2_token', ''))
        if not api_utils.ping():
            raise ValueError("DHIS2 server is unreachable or token is invalid (ping failed)")

        cls._validate_max_results(api_utils, config)
        cls._validate_default_coc(config)

    @classmethod
    def _validate_max_results(cls, api_utils, config):
        max_results = cls._validate_max_results_within_bounds(config)
        system_settings = api_utils.fetch_system_settings()
        if system_settings:
            key_data_quality_max_limit = system_settings.get('keyDataQualityMaxLimit', 500)
            if key_data_quality_max_limit < max_results:
                raise ValueError(
                    f"Configured max_results ({max_results}) exceeds system setting keyDataQualityMaxLimit ({key_data_quality_max_limit})"
                )

    @classmethod
    def _validate_max_results_within_bounds(cls, config):
        # Check the keyDataQualityMaxLimit in system settings is greater than or equal to the configured max_results
        max_results = config['server'].get('max_results', 500)
        if not (500 <= max_results <= 50000):
            raise ValueError(f"max_results must be between 500 and 50000, got {max_results}")
        return max_results


    def validate_structure(self, config: dict):
        self._validate_base_url(config['server']['base_url'])
        self._validate_api_token(config['server']['base_url'], config['server']['d2_token'])
        self._validate_max_results_within_bounds(config)
        #We need at least analyzer_stages or min_max_stages
        if 'analyzer_stages' not in config and 'min_max_stages' not in config:
            raise ValueError("Configuration must contain either 'analyzer_stages' or 'min_max_stages'")
        self._validate_unique_stage_name(config)

        if 'analyzer_stages' in config:
            for stage in config['analyzer_stages']:
                self._validate_stage(stage)
                self._validate_stage_params(stage)
                if stage['type'] in ['validation_rules', 'outlier']:
                    self._is_valid_duration(stage['params']['duration'], stage['name'])

        # Validate min_max stages
        if 'min_max_stages' in config:
            for stage in config['min_max_stages']:
                self._validate_min_max_stages(stage)


    @staticmethod
    def _validate_unique_stage_name(config):
        stage_names = [stage['name'] for stage in config['analyzer_stages']]
        duplicates = {name for i, name in enumerate(stage_names) if name in stage_names[:i]}
        if duplicates:
            raise ValueError(f"Duplicate stage names found: {', '.join(duplicates)}")



    def _validate_stage_params(self, stage):
        params = stage['params']
        stage_type = stage['type']
        if stage_type == 'validation_rules':
            required = ['validation_rule_group', 'destination_data_element', 'level', 'duration']
        elif stage_type == 'outlier':
            required = ['dataset', 'algorithm', 'destination_data_element', 'level', 'duration']
            self._validate_outlier_start_end_dates(stage)
        elif stage_type == 'min_max':
            required = ['dataset', 'destination_data_element']
        elif stage_type == 'integrity_checks':
            required = ['monitoring_group', 'period_type','dataset']
        else:
            raise ValueError(f"Unknown stage type '{stage_type}' in stage '{stage['name']}'")
        for param in required:
            if param not in params:
                raise ValueError(f"Missing parameter '{param}' in stage '{stage['name']}' of type '{stage_type}'")

    @staticmethod
    def _validate_stage(stage):
        if 'name' not in stage:
            raise ValueError("Stage missing 'name'")
        if 'type' not in stage:
            raise ValueError(f"Stage '{stage.get('name', 'UNKNOWN')}' missing 'type'")
        if 'params' not in stage:
            raise ValueError(f"Stage '{stage['name']}' missing 'params' section")


    @staticmethod
    def _validate_default_coc(config):
        api_utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )
        default_coc = config['server'].get('default_coc')
        #This can be blank, but then we need to check to see if HllvX50cXC0 exists as this is the default
        if not default_coc:
            default_coc = 'HllvX50cXC0'
        if not api_utils.fetch_category_option_combo_by_id(default_coc):
            raise ValueError(f"Default category option combo '{default_coc}' does not exist in the system.")


    @staticmethod
    def _is_valid_duration(value: str, stage_name: str) -> None:
        logging.debug("Validating duration for stage '%s': '%s'", stage_name, value)
        match = re.match(r"^\s*(\d+)\s+(\w+)\s*$", value.strip(), re.IGNORECASE)
        if not match:
            raise ValueError(
                f"Invalid duration format in stage '{stage_name}': '{value}'. "
                "Expected format like '12 monthly', '1 yearly', etc."
            )
        amount, unit = match.groups()
        if int(amount) <= 0:
            raise ValueError(f"Duration must be > 0 in stage '{stage_name}'")
        if unit.lower() not in TimeUnit.list():
            raise ValueError(
                f"Invalid period type '{unit}' in stage '{stage_name}'. "
                f"Must be one of: {', '.join(TimeUnit.list())}"
            )
    @staticmethod
    def _validate_base_url(url: str):
        if not url.startswith("http://") and not url.startswith("https://"):
            raise ValueError(f"Base URL must start with http:// or https://: '{url}'")
        if url.endswith("/"):
            raise ValueError(f"Base URL must not end with a trailing slash: '{url}'")

    @staticmethod
    def _validate_api_token(base_url: str, d2_token: str):
        import requests
        try:
            headers = {'Authorization': f'ApiToken {d2_token}'}
            ping_url = f"{base_url}/api/ping"
            response = requests.get(ping_url, headers=headers, timeout=5)
            if response.status_code != 200:
                raise ValueError(f"Invalid DHIS2 API token or server unreachable: {ping_url}")
        except requests.RequestException as e:
            raise ValueError(f"Failed to connect to DHIS2 API: {e}")

    @staticmethod
    def _validate_outlier_start_end_dates(stage):
        start_date = None
        end_date = None
        start_date_offset = stage['params'].get('start_date_offset', None)
        end_date_offset = stage['params'].get('end_date_offset', None)
        if start_date_offset is not None:
            ConfigManager._is_valid_duration(start_date_offset, stage['name'])
            start_date = Dhis2PeriodUtils.get_start_date_from_today(start_date_offset)
        if end_date_offset is not None:
            ConfigManager._is_valid_duration(end_date_offset, stage['name'])
            end_date = Dhis2PeriodUtils.get_start_date_from_today(end_date_offset)
        if start_date is not None and end_date is not None:
            if start_date > end_date:
                raise ValueError(
                    f"Start date offset '{start_date_offset}' must be greater than end date offset '{end_date_offset}' in stage '{stage['name']}'"
                )

    def _validate_datasets_exist(self, datasets):
        api_utils = Dhis2ApiUtils(
            base_url=self.config['server']['base_url'],
            d2_token=self.config['server']['d2_token']
        )
        for dataset in datasets:
            if not api_utils.fetch_dataset_by_id(dataset):
                raise ValueError(f"Dataset '{dataset}' does not exist in the system.")

    def _validate_data_element_groups_exist(self, groups):
        api_utils = Dhis2ApiUtils(
            base_url=self.config['server']['base_url'],
            d2_token=self.config['server']['d2_token']
        )
        for group in groups:
            if not api_utils.fetch_data_element_group_by_id(group):
                raise ValueError(f"Data element group '{group}' does not exist in the system.")

    def _validate_data_elements_exist(self, data_elements):
        api_utils = Dhis2ApiUtils(
            base_url=self.config['server']['base_url'],
            d2_token=self.config['server']['d2_token']
        )
        for data_element in data_elements:
            if not api_utils.fetch_data_element_by_id(data_element):
                raise ValueError(f"Data element '{data_element}' does not exist in the system.")

    def _validate_org_units_exist(self,    org_units):
        api_utils = Dhis2ApiUtils(
            base_url=self.config['server']['base_url'],
            d2_token=self.config['server']['d2_token']
        )
        for org_unit in org_units:
            if not api_utils.fetch_organisation_unit_by_id(org_unit):
                raise ValueError(f"Organisation unit '{org_unit}' does not exist in the system.")


    def _validate_min_max_stages(self,stage):
        required_keys = ['name', 'org_units', 'previous_periods', 'duration','completeness_threshold','groups']
        for key in required_keys:
            if key not in stage:
               raise ValueError(f"Missing '{key}' in min_max_stage '{stage.get('name', '<unnamed>')}'")
        if stage.get('datasets'):
            #Must contain at least one dataset
            if not isinstance(stage['datasets'], list) or not stage['datasets']:
                raise ValueError(f"'datasets' must be a non-empty list in min_max_stage '{stage.get('name', '<unnamed>')}'")
            self._validate_datasets_exist(stage['datasets'])
        if stage.get('data_element_groups'):
            #Must contain at least one data element group
            if not isinstance(stage['data_element_groups'], list) or not stage['data_element_groups']:
                raise ValueError(f"'data_element_groups' must be a non-empty list in min_max_stage '{stage.get('name', '<unnamed>')}'")
            self._validate_data_element_groups_exist(stage['data_element_groups'])
        if stage.get('data_elements'):
            #Must contain at least one data element
            if not isinstance(stage['data_elements'], list) or not stage['data_elements']:
                raise ValueError(f"'data_elements' must be a non-empty list in min_max_stage '{stage.get('name', '<unnamed>')}'")
            self._validate_data_elements_exist(stage['data_elements'])
        #We need at least one of datasets, data_element_groups or data_elements
        if not (stage.get('datasets') or stage.get('data_element_groups') or stage.get('data_elements')):
            raise ValueError(f"At least one of 'datasets', 'data_element_groups' or 'data_elements' must be specified in min_max_stage '{stage.get('name', '<unnamed>')}'")
        if stage.get('org_units') is None:
            raise ValueError(f"Organisation units must be specified in min_max_stage '{stage.get('name', '<unnamed>')}'")
        self._validate_org_units_exist(stage.get('org_units', []))
        self._is_valid_duration(stage.get('duration', '12 months'), stage.get('name', '<unnamed>'))
