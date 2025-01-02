import yaml


class ValidationMonitorConfigReader:
    def __init__(self, config_path):
        self.config = {}

        with open(config_path, 'r') as stream:
            self.config = yaml.safe_load(stream)

        self.validate_config()
        self.base_url = self.config['server']['base_url']
        self.d2_token = self.config['server']['d2_token']
        self.default_coc = self.config['server']['default_coc']
        self.max_concurrent_requests = self.max_concurrent_requests = self.\
            config['server'].get('max_concurrent_requests',                                                  10)
        self.decimal_places = self.config['server'].get('decimal_places', 3)

    def validate_config(self):
        if 'stages' not in self.config:
            raise ValueError("No stages defined in configuration")

        for stage in self.config['stages']:
            if 'name' not in stage:
                raise ValueError("Stage name not defined")
            if 'level' not in stage:
                raise ValueError("Organisation unit level not defined")
            if 'duration' not in stage and 'previous_periods' not in stage:
                raise ValueError("Duration  or previous periods not defined")
            if 'validation_rule_groups' not in stage and 'dataset' not in stage:
                raise ValueError("Validation rule groups or dataset not defined")
            if 'validation_rule_groups' in stage and 'dataset' in stage:
                raise ValueError("Both validation rule groups and dataset defined")
            if 'destination_data_element' not in stage:
                raise ValueError("Destination data element not defined")
            if 'dataset' in stage and 'previous_periods' not in stage:
                raise ValueError("No previous periods defined for dataset analysis")

        for key in self.config['server']:
            if key not in ['base_url', 'd2_token', 'default_coc', 'max_concurrent_requests', 'decimal_places']:
                raise ValueError(f"Invalid key '{key}' in server configuration")

    def get_config(self):
        return self.config

    def get_stages(self):
        return self.config['stages']

    def __getattr__(self, item):
        if item in self.config['server']:
            return self.config['server'][item]
        raise AttributeError(f"'ValidationMonitorConfigReader' object has no attribute '{item}'")
