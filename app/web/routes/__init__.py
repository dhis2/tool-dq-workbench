# app/web/routes/__init__.py

from .api_blueprint import api_bp

# Import all route modules so they attach routes to `api_bp`
from . import (
    index,
    run,
    run_stage,
    edit_server,
    new_outlier_stage,
    new_validation_rule_stage,
    edit_outlier_stage,
    edit_validation_rule_stage,
    delete_stage,
    api
)

def register_routes(app):
    app.register_blueprint(api_bp)
