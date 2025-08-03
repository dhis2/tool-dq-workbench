import yaml

from app.core.api_utils import Dhis2ApiUtils
import re
from app.core.time_unit import TimeUnit
import logging

class ConfigManager:
    def __init__(self, config_path, validate_structure=True, validate_runtime=True):
        with open(config_path, 'r') as stream:
            config = yaml.safe_load(stream)

        self.config = config
        if validate_structure:
            self.validate_structure(config)

        if validate_runtime:
            self._validate_runtime(config)

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

    @classmethod
    def validate_structure(cls, config: dict):
        cls._validate_base_url(config['server']['base_url'])
        cls._validate_api_token(config['server']['base_url'], config['server']['d2_token'])
        cls._validate_max_results_within_bounds(config)
        #We need at least analyzer_stages or min_max_stages
        if 'analyzer_stages' not in config and 'min_max_stages' not in config:
            raise ValueError("Configuration must contain either 'analyzer_stages' or 'min_max_stages'")
        cls._validate_unique_stage_name(config)

        if 'analyzer_stages' in config:
            for stage in config['analyzer_stages']:
                cls._validate_stage(stage)
                cls._validate_stage_params(stage)
                cls._is_valid_duration(stage['duration'], stage['name'])

        # Validate min_max stages
        if 'min_max_stages' in config:
            for stage in config['min_max_stages']:
                cls._validate_min_max_stages(stage)


    @staticmethod
    def _validate_unique_stage_name(config):
        stage_names = [stage['name'] for stage in config['analyzer_stages']]
        duplicates = set([name for name in stage_names if stage_names.count(name) > 1])
        if duplicates:
            raise ValueError(f"Duplicate stage names found: {', '.join(duplicates)}")

    @staticmethod
    def _validate_stage_params(stage):
        params = stage['params']
        stage_type = stage['type']
        if stage_type == 'validation_rules':
            required = ['validation_rule_group', 'destination_data_element']
        elif stage_type == 'outlier':
            required = ['dataset', 'algorithm', 'destination_data_element']
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
        if 'level' not in stage:
            raise ValueError(f"Stage '{stage['name']}' missing 'level'")
        if 'duration' not in stage:
            raise ValueError(f"Stage '{stage['name']}' missing 'duration'")
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
    def _validate_min_max_stages(stage):
        required_keys = ['name', 'datasets', 'org_units', 'previous_periods', 'completeness_threshold','groups']
        for key in required_keys:
            if key not in stage:
               raise ValueError(f"Missing '{key}' in min_max_stage '{stage.get('name', '<unnamed>')}'")
