import yaml

class ConfigManager:
    def __init__(self, config_path):
        with open(config_path, 'r') as stream:
            self.config = yaml.safe_load(stream)
        self._validate_config()

    def _validate_config(self):
        if 'stages' not in self.config:
            raise ValueError("No stages defined in configuration")

        for stage in self.config['stages']:
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
