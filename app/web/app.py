import argparse
import os
import subprocess
from copy import deepcopy

import requests.exceptions
import yaml
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

from app.core.api_utils import Dhis2ApiUtils
from app.web.utils.config_helpers import load_config, save_config, resolve_uid_name
from .routes import register_routes


def _configure_secret_key(app):
    secret_key = os.environ.get('FLASK_SECRET_KEY')
    if not secret_key:
        print("Warning: FLASK_SECRET_KEY not set. Using a temporary key for development.")
        secret_key = os.urandom(24)
    app.secret_key = secret_key
def _configure_app(app, config_path):
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
