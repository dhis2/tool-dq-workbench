from flask import Blueprint, current_app, redirect, url_for, flash

from app.core.config_loader import ConfigManager
from app.web.utils.config_helpers import save_config
from app.web.routes.api import api_bp


@api_bp.route('/delete-minmax-stage/<int:stage_index>', methods=['POST'], endpoint ='delete_minmax_stage')
def delete_minmax_stage_view(stage_index):
    config_path = current_app.config['CONFIG_PATH']
    cm = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False)
    config = cm.config

    if 0 <= stage_index < len(config['min_max_stages']):
        removed_stage = config['min_max_stages'].pop(stage_index)
        cm.save(config_path)
        flash(f"Deleted min max stage: {removed_stage['name']}", 'success')
    else:
        flash("Invalid stage index", 'danger')

    return redirect(url_for('ui.index'))
