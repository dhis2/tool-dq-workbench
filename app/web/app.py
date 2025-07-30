import argparse
import logging
import os
from flask import Flask
from flask_wtf import CSRFProtect
from .routes import register_routes
from app.core.config_loader import ConfigManager

def _configure_secret_key(app):
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not secret_key:
        print("Warning: FLASK_SECRET_KEY not set. Using a temporary key for development.")
        secret_key = os.urandom(24)
    app.secret_key = secret_key
def _configure_app(app, config_path, skip_validation):
    config_path = os.path.abspath(config_path)
    app.config['CONFIG_PATH'] = os.path.abspath(config_path)
    app.config['SKIP_VALIDATION'] = skip_validation
    validate = not skip_validation
    try:
        ConfigManager(config_path,
                      validate_structure=validate,
    validate_runtime=validate)
    except Exception as e:
        print(f"Failed to start due to invalid configuration:\n{e}")
        exit(1)


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
    args = parser.parse_args()

    app = create_app(args.config, skip_validation=args.skip_validation)
    print(f"Using config: {app.config['CONFIG_PATH']}")

    # Enable more verbose logging
    app.logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)

    # Print all registered routes for debugging
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule}")

    app.run(debug=True, use_reloader=False)  # use_reloader=False helps with PyCharm


if __name__ == '__main__':
    main()
