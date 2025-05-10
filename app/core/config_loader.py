import yaml

from app.core.api_utils import Dhis2ApiUtils
import re
from app.core.time_unit import TimeUnit
import logging

class ConfigManager:
    def __init__(self, config_path):
        with open(config_path, 'r') as stream:
            self.config = yaml.safe_load(stream)
        logging.debug("Config loaded: %s", self.config)
        self.validate_dict(self.config)
        logging.debug("Finished config validation")


    @classmethod
    def validate_dict(cls, config: dict):
        cls._validate_default_coc(config)
        if 'stages' not in config:
            raise ValueError("No stages defined in configuration")

        for stage in config['stages']:
            cls._validate_stage(stage)
            cls._validate_stage_params(stage)
            cls._is_valid_duration(stage['duration'], stage['name'])


    @staticmethod
    def _validate_stage_params(stage):
        params = stage['params']
        stage_type = stage['type']
        if stage_type == 'validation_rules':
            required = ['validation_rule_groups', 'destination_data_element']
        elif stage_type == 'outlier':
            required = ['dataset', 'algorithm', 'destination_data_element']
        elif stage_type == 'min_max':
            required = ['dataset', 'destination_data_element']
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
