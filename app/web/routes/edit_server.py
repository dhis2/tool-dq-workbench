import os

from flask import current_app, request, render_template, redirect, url_for, flash

from app.core.config_loader import ConfigManager
from app.web.routes.api import api_bp
from app.web.utils.config_helpers import save_config

@api_bp.route('/edit-server', methods=['GET', 'POST'], endpoint='edit_server')
def edit_server():
    config_path = current_app.config['CONFIG_PATH']
    abs_config_path = os.path.abspath(config_path)
    try:
        config = ConfigManager(config_path, config=None, validate_structure=False,
                               validate_runtime=False).config
    except Exception:
        config = {}

    server = config.setdefault('server', {})
    server.setdefault('base_url', '')
    server.setdefault('d2_token', '')
    server.setdefault('logging_level', 'INFO')
    server.setdefault('max_concurrent_requests', 5)
    server.setdefault('max_results', 500)
    server.setdefault('min_max_bulk_api_disabled', False)

    if request.method == 'POST':

        try:
            config['server']['base_url'] = request.form['base_url']
            new_token = request.form['d2_token'].strip()
            if new_token:
                config['server']['d2_token'] = new_token
            config['server']['logging_level'] = request.form['logging_level']
            config['server']['max_concurrent_requests'] = int(request.form['max_concurrent_requests'])
            config['server']['max_results'] = int(request.form['max_results'])
            config['server']['min_max_bulk_api_disabled'] = (
                request.form.get('min_max_bulk_api_disabled', 'false').lower() == 'true'
            )

            save_config(config_path, config)
            flash('Server configuration updated.', 'success')
            return redirect(url_for('ui.index'))

        except ValueError as e:
            flash(f"Failed to save server configuration: {e}", 'danger')
            # Fall through to re-render the form with current values

        except Exception as e:
            flash(f"Unexpected error: {e}", 'danger')
            return redirect(url_for('ui.index'))

        # Return form with the values user submitted
        return render_template("edit_server.html", server=config['server'],
                               config_path=abs_config_path)

    # GET request
    return render_template("edit_server.html", server=config['server'],
                           config_path=abs_config_path)
