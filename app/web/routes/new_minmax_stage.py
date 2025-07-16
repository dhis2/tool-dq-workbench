import requests
from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash

from app.core.api_utils import Dhis2ApiUtils
from app.core.config_loader import ConfigManager
from app.web.utils.config_helpers import load_config, save_config, resolve_uid_name
from app.web.routes.api import api_bp
# Utility to generate a blank minmax stage
def default_minmax_stage():
    return {
        'name': '',
        'datasets': [],
        'groups': [{'limitmedian': '', 'method': '', 'threshold': ''}],
        'orgunits': [],
        'previous_periods': 12
    }

@api_bp.route('/new-minmax-stage', methods=['GET', 'POST'], endpoint = 'new-minmax-stage')
def new_minmax_stage_view():
    server_config_path = current_app.config['CONFIG_PATH']

    if request.method == 'POST':
        config = load_config(server_config_path)
        if 'min_max_stage' not in config:
            config['min_max_stage'] = []

        deg_uid = request.form['monitoring_group']
        deg_name = deg_uid
        api_utils = Dhis2ApiUtils(
            base_url=config['server']['base_url'],
            d2_token=config['server']['d2_token']
        )