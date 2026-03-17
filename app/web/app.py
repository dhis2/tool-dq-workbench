import argparse
import logging
import os
import threading
import webbrowser
from waitress import serve

from flask import Flask

from app.core.config_loader import ConfigManager
from .routes import register_routes


def _configure_secret_key(app):
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not secret_key:
        logging.warning(
            "FLASK_SECRET_KEY is not set. A temporary key will be used, which means "
            "all sessions will be invalidated on restart. "
            "Set a stable key with: export FLASK_SECRET_KEY=$(python -c \"import secrets; print(secrets.token_hex(32))\")"
        )
        secret_key = os.urandom(24)
    app.secret_key = secret_key
def _configure_app(app, config_path, skip_validation):
    config_path = os.path.abspath(config_path)
    app.config['CONFIG_PATH'] = os.path.abspath(config_path)
    app.config['SKIP_VALIDATION'] = skip_validation
    validate = not skip_validation
    try:
        ConfigManager(config_path,
                      config = None,
                      validate_structure=validate,
    validate_runtime=validate)
    except Exception as e:
        raise RuntimeError(f"Failed to start due to invalid configuration: {e}") from e


def create_app_from_env():
    """Gunicorn-compatible factory that reads CONFIG_PATH from the environment.
    Used as the application callable in Docker: gunicorn "app.web.app:create_app_from_env()"

    If CONFIG_PATH does not exist but DHIS2_BASE_URL and DHIS2_API_TOKEN are set,
    a minimal config file is bootstrapped automatically so the app starts without
    any pre-existing configuration.
    """
    config_path = os.environ.get('CONFIG_PATH', '/app/config/config.yml')

    if not os.path.exists(config_path):
        base_url = os.environ.get('DHIS2_BASE_URL', '').rstrip('/')
        api_token = os.environ.get('DHIS2_API_TOKEN', '')
        if base_url and api_token:
            _bootstrap_config(config_path, base_url, api_token)
        else:
            raise RuntimeError(
                f"Config file not found at '{config_path}'. "
                "Either mount a config file or set DHIS2_BASE_URL and DHIS2_API_TOKEN "
                "environment variables to bootstrap one automatically."
            )

    return create_app(config_path)


def _resolve_config_path(cli_arg):
    """Resolve config path: CLI arg > DQ_CONFIG_PATH env var > platform default.

    DQ_CONFIG_PATH is a new env var for the desktop use case.
    The existing CONFIG_PATH env var remains Docker/gunicorn-only (read by create_app_from_env).
    """
    import sys
    from pathlib import Path
    if cli_arg:
        return Path(cli_arg)
    env = os.environ.get('DQ_CONFIG_PATH')
    if env:
        return Path(env)
    if sys.platform == 'win32':
        return Path.home() / 'Documents' / 'DQ Workbench' / 'config.yml'
    return Path.home() / '.config' / 'dq-workbench' / 'config.yml'


def _write_blank_config(path):
    """Write a minimal blank config to path, creating parent directories.

    Unlike the existing _bootstrap_config() (which takes real credentials for Docker),
    this writes an empty config for first-run onboarding — credentials are filled in
    via the web UI.
    """
    import yaml  # yaml is not imported at module level; use local import like _bootstrap_config
    path.parent.mkdir(parents=True, exist_ok=True)
    minimal = {
        'server': {
            'base_url': '',
            'd2_token': '',
            'logging_level': 'INFO',
            'max_concurrent_requests': 5,
            'max_results': 500,
        },
        'analyzer_stages': [],
    }
    with open(path, 'w') as f:
        yaml.dump(minimal, f, default_flow_style=False)
    logging.info(f"Created blank config at '{path}'")


def _bootstrap_config(config_path, base_url, api_token):
    """Write a minimal YAML config seeded with the given server details."""
    import yaml
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    minimal = {
        'server': {
            'base_url': base_url,
            'd2_token': api_token,
            'logging_level': 'INFO',
            'max_concurrent_requests': 5,
            'max_results': 500,
        },
        'analyzer_stages': [],
    }
    with open(config_path, 'w') as f:
        yaml.dump(minimal, f, default_flow_style=False)
    logging.info(f"Bootstrapped minimal config at '{config_path}'")


def create_app(config_path, skip_validation=False):
    app = Flask(__name__)
    _configure_secret_key(app)
    _configure_app(app, config_path, skip_validation)

    # Add logging configuration
    _configure_logging(app)

    register_routes(app)
    return app


def _configure_logging(app):
    if app.debug:
        # In debug mode, set up console logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s %(name)s: %(message)s',
            handlers=[logging.StreamHandler()]
        )
        app.logger.setLevel(logging.DEBUG)
    else:
        # Production logging
        logging.basicConfig(level=logging.INFO)


def main():
    parser = argparse.ArgumentParser(description="Flask UI for Data Quality Monitor")
    parser.add_argument('--config', default=None, help='Path to YAML config file (default: platform-appropriate location)')
    parser.add_argument('--skip-validation', action='store_true',
                        help='Skip config validation (use for onboarding only)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable Flask debug mode (development only)')
    args = parser.parse_args()

    config_path = _resolve_config_path(args.config)
    skip_validation = args.skip_validation

    if not config_path.exists():
        logging.info(f"No config found at '{config_path}'. Creating blank config.")
        _write_blank_config(config_path)
        skip_validation = True

    app = create_app(str(config_path), skip_validation=skip_validation)
    print(f"Using config: {app.config['CONFIG_PATH']}")

    if args.debug:
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        print("Registered routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule.endpoint}: {rule.rule}")

    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    print("=" * 60)
    print("DQ Workbench is running at http://127.0.0.1:5000")
    print("Close this window to stop the server.")
    print("=" * 60)
    serve(app, host="127.0.0.1", port=5000)


if __name__ == '__main__':
    main()
