# web/utils/config_helpers.py
import logging
from pprint import pprint

import requests.exceptions
import yaml
from flask import current_app

from app.core.config_loader import ConfigManager

def load_config(config_path):
    validate = not current_app.config.get('SKIP_VALIDATION', False)
    return ConfigManager(config_path, validate_structure=validate,
                         validate_runtime=validate).config

def save_config(config_path, config):
    validate = not current_app.config.get('SKIP_VALIDATION', False)
    if validate:
        ConfigManager.validate_structure(config)
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

