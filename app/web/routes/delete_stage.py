from flask import Blueprint, current_app, redirect, url_for, flash
from app.web.utils.config_helpers import save_config
from app.web.routes.api import api_bp
from app.core.config_loader import ConfigManager


@api_bp.route('/delete-stage/<int:stage_index>', methods=['POST'], endpoint ='delete_stage')
def delete_stage_view(stage_index):
    config_path = current_app.config['CONFIG_PATH']
    config = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config

    if 0 <= stage_index < len(config['analyzer_stages']):
        removed_stage = config['analyzer_stages'].pop(stage_index)
        save_config(config_path, config)
        flash(f"Deleted stage: {removed_stage['name']}", 'success')
    else:
        flash("Invalid stage index", 'danger')

    return redirect(url_for('ui.index'))
