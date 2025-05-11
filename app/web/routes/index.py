# app/web/routes/index.py
from flask import current_app, render_template
import yaml
from .ui_blueprint import ui_bp

@ui_bp.route('/')
def index():
    with open(current_app.config['CONFIG_PATH']) as f:
        config = yaml.safe_load(f)
    return render_template("index.html", config=config)
