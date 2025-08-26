import logging
import random
import string

import requests


class Dhis2ApiUtils:
    def __init__(self, base_url, d2_token=None, require_token=True):
        self.base_url = base_url
        if require_token and not d2_token:
            raise ValueError("A DHIS2 API token is required unless 'require_token=False' for testing.")
        self.d2_token = d2_token
        self.request_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'Authorization': f'ApiToken {d2_token}'
        }

    async def get_system_info(self, session):
        url = f'{self.base_url}/api/system/info.json'
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()



    def post_metadata(self, metadata):
        """
        Post metadata to the DHIS2 API.
        Note that this method is synchronous so should not be used in an async context.
        :param metadata: Metadata to post (dict).
        :return: Response from the API.
        """
        url = f'{self.base_url}/api/metadata'
        #Add the 'Content-Type' header if not already set
        if 'Content-Type' not in self.request_headers:
            self.request_headers['Content-Type'] = 'application/json'
        response = requests.post(url, json=metadata, headers=self.request_headers)
        response.raise_for_status()
        return response


    async def get_server_version(self, session):
        settings = await self.get_system_info(session)
        version = settings.get('version')
        if not version:
            raise ValueError("Server version not found in system settings")

        # Strip any suffix like '-SNAPSHOT'
        base_version = version.split('-')[0]
        parts = base_version.split('.')

        if len(parts) < 2:
            raise ValueError(f"Unexpected version format: {version}")

        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0

        return {
            'major': major,
            'minor': minor,
            'patch': patch,
            'snapshot': 'SNAPSHOT' in version
        }

    async def get_organisation_units_at_level(self, level, session, semaphore):
        url = f'{self.base_url}/api/organisationUnits.json?filter=level:eq:{level}&fields=id&paging=false'
        async with semaphore:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return [ou['id'] for ou in data['organisationUnits']]

    async def fetch_datavalue_sets(self, query_params, session):
        url = f'{self.base_url}/api/dataValueSets.json'
        async with session.get(url, params=query_params) as response:
            if response.status != 200:
                logging.error(f"Failed to fetch data value sets: {response.status}")
                logging.error(await response.text())
                raise requests.exceptions.RequestException(f"Failed to fetch data value sets: {response.status}")
            return await response.json()

    async def create_and_post_data_value_set(self, validation_rule_values, session):
        datavalue_set = {
            'dataValues': validation_rule_values
        }
        url = f'{self.base_url}/api/dataValueSets'
        async with session.post(url, json=datavalue_set) as response:
            if response.status != 200:
                logging.error(f"Failed to post data value set: {response.status}")
                logging.error(await response.text())
                raise requests.exceptions.RequestException(f"Failed to post data value set: {response.status}")
            return await response.json()

    # --- Generic Metadata Utilities ---
    def fetch_metadata_list(self, endpoint, key=None, filters=None, fields=None, extra_params=None):
        if fields is None:
            fields = ['id', 'name']
        if extra_params is None:
            extra_params = {'paging': 'false'}
        if filters is None:
            filters = []

        base_url = f"{self.base_url.rstrip('/')}/api/{endpoint}.json"
        params = {
            'fields': ','.join(fields),
            'filter': filters,
            **extra_params
        }

        logging.debug(f"Fetching metadata from URL: {base_url} with params: {params}")
        resp = requests.get(base_url, headers=self.request_headers, params=params)
        logging.debug("Got response "f"status: {resp.status_code}, content: {resp.text[:100]}...")
        resp.raise_for_status()
        json_resp = resp.json()
        return json_resp.get(key, []) if key else json_resp

    def fetch_metadata_item_by_id(self, endpoint, uid):
        """
        Fetch a single metadata item (e.g., dataElement) by UID.
        """
        # Supported endpoints
        allowed_endpoints = {'dataElements', 'dataSets', 'validationRuleGroups', 'categoryOptionCombos',
                             'dataElementGroups'}
        if endpoint not in allowed_endpoints:
            raise ValueError(f"Invalid endpoint: {endpoint}")

        # Validate UID
        if not uid.isalnum() or len(uid) != 11 or not uid[0].isalpha():
            raise ValueError(f"Invalid UID: {uid}")

        url = f"{self.base_url.rstrip('/')}/api/{endpoint}/{uid}?fields=id,name"

        response = requests.get(url, headers=self.request_headers)
        response.raise_for_status()
        return response.json()

    # --- Specific Wrappers ---
    def fetch_data_elements(self, filters=None, fields=None, extra_params=None):
        return self.fetch_metadata_list('dataElements', 'dataElements', filters, fields, extra_params)

    def fetch_data_sets(self, filters=None, fields=None, extra_params=None):
        if fields is None:
            fields = ['id', 'name']
        return self.fetch_metadata_list('dataSets', 'dataSets', filters, fields, extra_params)

    def fetch_validation_rule_groups(self, filters=None, fields=None, extra_params=None):
        return self.fetch_metadata_list('validationRuleGroups', 'validationRuleGroups', filters, fields, extra_params)

    def fetch_data_element_groups(self, filters=None, fields=None, extra_params=None):
        return self.fetch_metadata_list('dataElementGroups', 'dataElementGroups', filters, fields, extra_params)

    def fetch_data_element_by_id(self, uid):
        resp = self.fetch_metadata_list('dataElements', 'dataElements', filters=[f'id:eq:{uid}'], fields=['id', 'name'])
        return  resp[0] if resp else None

    def fetch_organisation_unit_by_id(self, uid):
        resp = self.fetch_metadata_list('organisationUnits', 'organisationUnits', filters=[f'id:eq:{uid}'], fields=['id', 'name'])
        return resp[0] if resp else None

    def fetch_data_element_group_by_id(self, uid):
        resp = self.fetch_metadata_list('dataElementGroups', 'dataElementGroups', filters=[f'id:eq:{uid}'], fields=['id', 'name'])
        return resp[0] if resp else None

    def fetch_dataset_by_id(self, uid):
        resp = self.fetch_metadata_list('dataSets', 'dataSets', filters=[f'id:eq:{uid}'], fields=['id', 'name'])
        return resp[0] if resp else None

    def fetch_validation_rule_group_by_id(self, uid):
        resp = self.fetch_metadata_list('validationRuleGroups', 'validationRuleGroups', filters=[f'id:eq:{uid}'], fields=['id', 'name'])
        return resp[0] if resp else None

    def fetch_category_option_combo_by_id(self, uid):
        resp = self.fetch_metadata_list('categoryOptionCombos', 'categoryOptionCombos', filters=[f'id:eq:{uid}'], fields=['id', 'name'])
        return resp[0] if resp else None

    def fetch_me(self):
        url = f"{self.base_url.rstrip('/')}/api/me"
        response = requests.get(url, headers=self.request_headers)
        response.raise_for_status()
        return response.json()

    def ping(self):
        try:
            response = requests.get(f"{self.base_url}/api/system/ping", headers=self.request_headers)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    # --- Import Summary Logging ---
    @staticmethod
    def parse_import_summary(import_summary):
        if import_summary.get('status') == 'OK':
            response = import_summary.get('response', {})
            import_count = response.get('importCount', {})
            logging.info(
                f"Imported: {import_count.get('imported', 0)}, "
                f"Updated: {import_count.get('updated', 0)}, "
                f"Ignored: {import_count.get('ignored', 0)}, "
                f"Deleted: {import_count.get('deleted', 0)}"
            )
            return {
                "status": "OK",
                "imported": import_count.get('imported', 0),
                "updated": import_count.get('updated', 0),
                "ignored": import_count.get('ignored', 0),
                "deleted": import_count.get('deleted', 0)
            }
        else:
            logging.error(f"Error posting data value set: {import_summary.get('status')}")
            logging.error(import_summary)
            return {
                "status": import_summary.get('status', 'UNKNOWN'),
                "error": import_summary
            }

    @staticmethod
    def generate_uid():
        first_letter = random.choice(string.ascii_lowercase)
        last_part = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        return first_letter + last_part

    def fetch_system_settings(self):
        """
        Fetch system settings from the DHIS2 API.
        """
        url = f"{self.base_url.rstrip('/')}/api/systemSettings"
        response = requests.get(url, headers=self.request_headers)
        response.raise_for_status()
        return response.json()

    def get_metadata_integrity_checks(self):
        # GET /api/dataIntegrity
        url = f"{self.base_url}/api/dataIntegrity"
        headers = {k: v for k, v in self.request_headers.items() if k.lower() != 'content-type'}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
