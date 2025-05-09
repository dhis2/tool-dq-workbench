from flask import Blueprint, current_app, render_template
import yaml

from app.web.routes.api_blueprint import api_bp


@api_bp.route('/')
def index():
    with open(current_app.config['CONFIG_PATH']) as f:
        config = yaml.safe_load(f)
    return render_template("index.html", config=config)
