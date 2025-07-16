# app/web/routes/index.py
from flask import current_app, render_template
import yaml
from .ui_blueprint import ui_bp

@ui_bp.route('/min_max_index')
def min_max_index():
    with open(current_app.config['CONFIG_PATH']) as f:
        config = yaml.safe_load(f)
    min_max_stage_exists = any(stage.get('name') for stage in config['min_max_stages'])
    return render_template("index_minmax.html", config=config, min_max_stage_exists=min_max_stage_exists)
