from flask import Blueprint, current_app, redirect, url_for, flash
from app.web.utils.config_helpers import load_config, save_config
from app.web.routes.api_blueprint import api_bp


@api_bp.route('/delete-stage/<int:stage_index>', methods=['POST'], endpoint ='delete_stage')
def delete_stage_view(stage_index):
    config_path = current_app.config['CONFIG_PATH']
    config = load_config(config_path)

    if 0 <= stage_index < len(config['stages']):
        removed_stage = config['stages'].pop(stage_index)
        save_config(config_path, config)
        flash(f"Deleted stage: {removed_stage['name']}", 'success')
    else:
        flash("Invalid stage index", 'danger')

    return redirect(url_for('api.index'))
