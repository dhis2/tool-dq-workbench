import asyncio
import logging
import requests
from flask import current_app, request, render_template, redirect, url_for, flash
from copy import deepcopy

from app.analyzers.integrity_analyzer import IntegrityCheckAnalyzer
from app.core.api_utils import Dhis2ApiUtils
from app.web.utils.config_helpers import save_config
from app.web.routes.api import api_bp
from app.core.config_loader import ConfigManager
from app.core.uid_utils import UidUtils


def default_integrity_stage():
    """Utility to generate a blank integrity stage"""
    uid = UidUtils.generate_uid()
    return {
        'name': '',
        'uid': uid,
        'active': True,
        'type': 'integrity_checks',
        'level': 1,
        'params': {
            'monitoring_group': '',
            'period_type': 'Monthly',
            'dataset': ''
        }
    }

def validate_integrity_stage(stage):
    """Validate integrity stage configuration"""
    if not stage.get('name'):
        raise ValueError("Stage name cannot be empty")
    if not stage.get('uid'):
        raise ValueError("Stage UID cannot be empty")
    if not stage.get('params', {}).get('monitoring_group'):
        raise ValueError("Monitoring group must be specified")
    if not stage.get('params', {}).get('period_type'):
        raise ValueError("Period type must be specified")

def get_data_element_group_name(api_utils, deg_uid):
    """Fetch data element group name, return UID if fetch fails"""
    try:
        deg_name = api_utils.fetch_data_element_group_by_id(deg_uid)
        logging.debug("Fetched data element group name: %s", deg_name)
        return deg_name.get('name', deg_uid) if deg_name else deg_uid
    except requests.exceptions.RequestException:
        flash(f"Warning: Failed to fetch data element group name for {deg_uid}", 'warning')
        return deg_uid




@api_bp.route('/integrity-stage', methods=['GET', 'POST'], endpoint='new_integrity_stage')
@api_bp.route('/integrity-stage/<int:stage_index>', methods=['GET', 'POST'], endpoint='edit_integrity_stage')
def integrity_stage_view(stage_index=None):
    """Unified view for creating new or editing existing integrity stages"""
    config_path = current_app.config['CONFIG_PATH']
    is_edit = stage_index is not None

    try:
        config = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    # Initialize API utils
    api_utils = Dhis2ApiUtils(
        base_url=config['server']['base_url'],
        d2_token=config['server']['d2_token']
    )

    # Get or create stage
    if is_edit:
        # Editing existing stage
        if stage_index >= len(config.get('analyzer_stages', [])):
            flash('Stage not found.', 'danger')
            return redirect(url_for('ui.index'))

        stage = config['analyzer_stages'][stage_index]

        if stage.get('type') != 'integrity_checks':
            flash('Only the integrity check stage can be edited here.', 'danger')
            return redirect(url_for('ui.index'))
    else:
        # Creating new stage
        stage = default_integrity_stage()
        if 'analyzer_stages' not in config:
            config['analyzer_stages'] = []

    # Get data element group name for display
    deg_uid = stage['params'].get('monitoring_group', '')
    deg_name = get_data_element_group_name(api_utils, deg_uid) if deg_uid else ''


    if request.method == 'POST':
        # Update stage from form data
        stage['name'] = request.form['stage_name']
        stage['params']['level'] = int(request.form['orgunit_level'])
        stage['params']['duration'] = request.form['duration']
        stage['params']['monitoring_group'] = request.form['monitoring_group']
        stage['params']['period_type'] = request.form['period_type']

        # Handle UID generation/validation
        if not is_edit and not stage.get('uid'):
            stage['uid'] = UidUtils.generate_uid()
        elif is_edit:
            stage['uid'] = stage['uid'].strip()

        # Handle active status (only relevant for editing)
        if is_edit:
            logging.debug("Stage active status: %s", request.form.get('active', 'off'))
            stage['active'] = request.form.get('active', 'off') == 'on'

        # Get updated data element group name for validation feedback
        new_deg_uid = request.form['monitoring_group']
        if new_deg_uid != deg_uid:
            deg_name = get_data_element_group_name(api_utils, new_deg_uid)
            if not is_edit:
                stage['params']['dataelement_group_name'] = deg_name

        try:
            # Validate the stage
            validate_integrity_stage(stage)

            # Add new stage to config if creating
            if not is_edit:
                config['analyzer_stages'].append(stage)

            # Validate and save config
            ConfigManager.validate_structure(config)
            save_config(config_path, config)

            action = "Updated" if is_edit else "Added"
            flash(f"{action} integrity stage: {stage['name']}", 'success')
            return redirect(url_for('ui.index'))

        except ValueError as e:
            flash(f"Error saving stage: {e}", 'danger')
            # For new stages that fail validation, render with error but don't save
            if not is_edit:
                return render_template(
                    "stage_form_integrity_checks.html",
                    stage=stage,
                    edit=False,
                    deg_name=deg_name
                )

    # Render form (GET request or POST with validation errors)
    return render_template(
        "stage_form_integrity_checks.html",
        stage=deepcopy(stage) if is_edit else stage,
        edit=is_edit,
        deg_name=deg_name
    )


@api_bp.route('/integrity-stage/create-missing-des', methods=['GET', 'POST'], endpoint='create_missing_des')
def create_missing_data_elements():
    """View and create missing data elements for integrity checks"""
    config_path = current_app.config['CONFIG_PATH']

    try:
        config = ConfigManager(config_path, config=None, validate_structure=True, validate_runtime=False).config
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('ui.index'))

    # Initialize API utils
    d2_token = config['server'].get('d2_token')
    base_url = config['server']['base_url']
    api_utils = Dhis2ApiUtils(
        base_url=base_url,
        d2_token=d2_token
    )

    request_headers = {
        'Authorization': f'ApiToken {d2_token}',
        'Content-Type': 'application/json'
    }


    integrity_analyzer = IntegrityCheckAnalyzer(config,
                                               base_url=base_url,
                                                headers=request_headers)

    missing_checks = integrity_analyzer.get_integrity_checks_no_data_elements()

    if request.method == 'POST':
        created = []
        failed = []
        for check in missing_checks:
            try:
                de_payload = {
                    "name": f"[MI] {check['displayName']}",
                    "shortName": f"MI {check['code'][:40]}",  # DHIS2 shortName max 50 chars
                    "code": f"MI_{check['code']}",
                    "valueType": "TEXT",
                    "domainType": "AGGREGATE",
                    "aggregationType": "NONE",
                    "zeroIsSignificant": True,
                }
                # Create the data element
                response = api_utils.create_data_element(de_payload)
            except Exception as e:
                failed.append((check['code'], str(e)))

        flash(f"Created {len(created)} data elements.", 'success')
        if failed:
            flash(f"Failed to create: {failed}", 'danger')
        return redirect(url_for('api.create_missing_des'))

    return render_template('create_missing_des.html', missing_checks=missing_checks)