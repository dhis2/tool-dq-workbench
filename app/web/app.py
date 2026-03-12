import argparse
import logging
import os

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
    Used as the application callable in Docker: gunicorn app.web.app:create_app_from_env
    """
    config_path = os.environ.get('CONFIG_PATH', '/app/config/config.yml')
    return create_app(config_path)


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
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    parser.add_argument('--skip-validation', action='store_true',
                        help='Skip config validation (use for onboarding only)')
    parser.add_argument('--debug', action='store_true',
                        help='Enable Flask debug mode (development only)')
    args = parser.parse_args()

    app = create_app(args.config, skip_validation=args.skip_validation)
    print(f"Using config: {app.config['CONFIG_PATH']}")

    if args.debug:
        app.logger.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        print("Registered routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule.endpoint}: {rule.rule}")

    app.run(debug=args.debug, use_reloader=False)


if __name__ == '__main__':
    main()
