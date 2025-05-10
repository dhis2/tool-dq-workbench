import argparse
import os
from flask import Flask
from .routes import register_routes
from app.core.config_loader import ConfigManager

def _configure_secret_key(app):
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not secret_key:
        print("Warning: FLASK_SECRET_KEY not set. Using a temporary key for development.")
        secret_key = os.urandom(24)
    app.secret_key = secret_key
def _configure_app(app, config_path):
    config_path = os.path.abspath(config_path)
    try:
        ConfigManager(config_path)
    except Exception as e:
        print(f"Failed to start due to invalid configuration:\n{e}")
        exit(1)
    app.config['CONFIG_PATH'] = os.path.abspath(config_path)

def create_app(config_path):
    app = Flask(__name__)
    _configure_secret_key(app)
    _configure_app(app, config_path)
    register_routes(app)
    return app

def main():
    parser = argparse.ArgumentParser(description="Flask UI for Data Quality Monitor")
    parser.add_argument('--config', required=True, help='Path to YAML config file')
    args = parser.parse_args()

    app = create_app(args.config)
    print(f"Using config: {app.config['CONFIG_PATH']}")
    app.run(debug=True)


if __name__ == '__main__':
    main()
