# app/web/routes/index.py
from flask import current_app, render_template
import yaml
from .ui_blueprint import ui_bp

@ui_bp.route('/')
def index():
    with open(current_app.config['CONFIG_PATH']) as f:
        config = yaml.safe_load(f)
    integrity_stage_exists = any(stage.get('type') == 'integrity_checks' for stage in config['analyzer_stages'])
    return render_template("index.html", config=config, integrity_stage_exists=integrity_stage_exists)
