from flask import Blueprint, current_app, request, render_template, redirect, url_for, flash
from app.web.utils.config_helpers import load_config, save_config
from app.web.routes.api import api_bp

@api_bp.route('/edit-server', methods=['GET', 'POST'], endpoint='edit_server')
def edit_server():
    config_path = current_app.config['CONFIG_PATH']

    if request.method == 'POST':
        config = load_config(config_path)

        config['server']['min_max_bulk_api_disabled'].setdefault('min_max_bulk_api_disabled', False)

        config['server']['base_url'] = request.form['base_url']
        new_token = request.form['d2_token'].strip()
        if new_token:
            config['server']['d2_token'] = new_token
        config['server']['logging_level'] = request.form['logging_level']
        config['server']['max_concurrent_requests'] = int(request.form['max_concurrent_requests'])
        config['server']['max_results'] = int(request.form['max_results'])
        config['server']['min_max_bulk_api_disabled'] = request.form.get('min_max_bulk_api_disabled', 'false').lower() == 'true'

        save_config(config_path, config)

        flash('Server configuration updated.', 'success')
        return redirect(url_for('ui.index'))

    config = load_config(config_path)
    return render_template("edit_server.html", server=config['server'])
