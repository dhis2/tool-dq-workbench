# web/utils/config_helpers.py

import yaml

def load_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def save_config(config_path, config):
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

def resolve_uid_name(fetch_fn, uid):
    """
    Try to fetch an object's name using its UID via the given fetch function.
    Falls back to the UID if the name cannot be resolved.
    """
    try:
        obj = fetch_fn(uid)
        return obj.get("name", uid)
    except Exception:
        return uid
