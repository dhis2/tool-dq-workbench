# web/utils/config_helpers.py
import requests.exceptions
import yaml

def load_config(config_path):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def save_config(config_path, config):
    with open(config_path, 'w') as f:
        yaml.dump(config, f)

def resolve_uid_name(fetch_fn, uid):
    try:
        obj = fetch_fn(uid)
        return obj.get("name", uid)
    except Exception as e:
        print(f"[resolve_uid_name] Failed to resolve UID {uid}: {e}")
        return uid
