# app/web/routes/__init__.py

from .api import api_bp
from .ui_blueprint import ui_bp

from . import (
    index,
    index_minmax,
    run,
    run_stage,
    edit_server,
    edit_outlier_stage,
    edit_validation_rule_stage,
    edit_min_max_stage,
    run_minmax_stage,
    delete_minmax_stage,
    edit_integrity_stage,
    delete_stage,
    api
)

def register_routes(app):
    app.register_blueprint(api_bp)
    app.register_blueprint(ui_bp)