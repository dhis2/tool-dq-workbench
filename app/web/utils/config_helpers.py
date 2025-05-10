# web/utils/config_helpers.py
import requests.exceptions
import yaml
from app.core.config_loader import ConfigManager

def load_config(config_path):
    manager = ConfigManager(config_path)
    return manager.config

def save_config(config_path, config):
    ConfigManager.validate_dict(config)
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

def resolve_uid_name(fetch_fn, uid):
    try:
        obj = fetch_fn(uid)
        return obj.get("name", uid)
    except Exception as e:
        print(f"[resolve_uid_name] Failed to resolve UID {uid}: {e}")
        return uid
