# web/utils/config_helpers.py
import logging
import yaml
from app.core.config_loader import ConfigManager

def save_config(config_path, config):
        try:
            ConfigManager(config_path,
                      config=config,
                      validate_structure=True,
                      validate_runtime=False)
            with open(config_path, 'w') as f:
                yaml.dump(config, f)
        except ValueError as e:
            logging.error(f"Failed to validate config before saving: {e}")
            raise ValueError(f"Configuration validation failed: {e}")


