import yaml

from app.core.api_utils import Dhis2ApiUtils


class ConfigManager:
    def __init__(self, config_path):
        with open(config_path, 'r') as stream:
            self.config = yaml.safe_load(stream)
        self._validate_config()


    def _validate_config(self):
        self._validate_default_coc(self.config)
        if 'stages' not in self.config:
            raise ValueError("No stages defined in configuration")


        for stage in self.config['stages']:
            self._validate_stage(stage)
            self._validate_stage_params(stage)


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

