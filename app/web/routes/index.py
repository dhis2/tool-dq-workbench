# app/web/routes/index.py
from flask import current_app, flash, redirect, render_template, url_for
import yaml
from .ui_blueprint import ui_bp
from pathlib import Path

@ui_bp.route('/')
def index():
    config_path = current_app.config.get('CONFIG_PATH')
    config = {}
    stages = []
    has_server = False
    integrity_stage_exists = False
    load_error = None

    try:
        if not config_path:
            raise RuntimeError("CONFIG_PATH is not set in app config.")
        if not Path(config_path).is_file():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        # Required server section
        server = config.get('server') or {}
        has_server = bool(server.get('base_url') and server.get('d2_token'))

        # Optional analyzer_stages section
        raw_stages = config.get('analyzer_stages') or []
        # only keep dict-like items to be safe
        stages = [s for s in raw_stages if isinstance(s, dict)]

        integrity_stage_exists = any(
            (s.get('type') == 'integrity_checks') for s in stages
        )

    except Exception as e:
        # Don't crash—render the page with an error message
        load_error = str(e)

    startup_warning = current_app.config.pop('STARTUP_WARNING', None)
    if startup_warning:
        message, category = startup_warning
        flash(message, category)
        return redirect(url_for('api.edit_server'))

    if not load_error and not has_server:
        flash("Welcome \u2014 please enter your DHIS2 server details to get started.", "info")
        return redirect(url_for('api.edit_server'))

    return render_template(
        "index.html",
        config=config,
        stages=stages,
        integrity_stage_exists=integrity_stage_exists,
        has_server=has_server,
        load_error=load_error,
    )
