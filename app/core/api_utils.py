import logging
import random
import string

import requests
from urllib.parse import urljoin

class Dhis2ApiUtils:
    def __init__(self, base_url, d2_token=None, require_token=True):
        self.base_url = base_url
        if require_token and not d2_token:
            raise ValueError("A DHIS2 API token is required unless 'require_token=False' for testing.")
        self.d2_token = d2_token
        self.request_headers = {
            'Content-Type': 'application/json'
        }

        if d2_token:
            self.request_headers['Authorization'] = f'ApiToken {d2_token}'


    async def get_system_info(self, session):
        url = f'{self.base_url}/api/systemSettings'
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def get_server_version(self, session):
        settings = await self.get_system_info(session)
        version = settings.get('version')
        if version:
            if 'SNAPSHOT' in version:
                major, minor = version.split('-')[0].split('.')
                return {
                    'major': int(major),
                    'minor': int(minor),
                    'patch': 0,
                    'snapshot': True
                }
            elif version:
                major, minor, patch = version.split('.')
                return {
                    'major': int(major),
                    'minor': int(minor),
                    'patch': int(patch),
                    'snapshot': False
                }
        else:
            raise ValueError("Server version not found in system settings")
        return None


    async def get_organisation_units_at_level(self, level, session):
        url = f'{self.base_url}/api/organisationUnits.json?filter=level:eq:{level}&fields=id&paging=false'
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
        """
        Fetch metadata from a DHIS2 endpoint.

        Parameters:
        - endpoint (str): DHIS2 endpoint (e.g., 'dataElements', 'dataSets')
        - key (Optional[str]): Optional top-level key to extract from the response (e.g., 'dataElements').
                                If not provided, returns the full JSON response.
        - filters (Optional[list[str]]): List of filter strings, e.g. ["id:eq:xyz", "name:ilike:foo"]
        - fields (Optional[list[str]]): List of fields to return. Default: ['id', 'name']
        - extra_params (Optional[dict]): Additional query parameters. Default: {'paging': 'false'}

        Returns:
        - dict or list: The full response dict, or the extracted value under `key` if provided.
        """
        if fields is None:
            fields = ['id', 'name']
        if extra_params is None:
            extra_params = {'paging': 'false'}
        if filters is None:
            filters = []

        base_url = f"{self.base_url.rstrip('/')}/api/{endpoint}.json"
        params = {
            'fields': ','.join(fields),
            **extra_params
        }

        for filter_str in filters:
            params.setdefault('filter', []).append(filter_str)

        logging.debug(f"Fetching metadata from URL: {base_url} with params: {params}")
        resp = requests.get(base_url, headers=self.request_headers, params=params)
        resp.raise_for_status()
        json_resp = resp.json()
        return json_resp.get(key, []) if key else json_resp

    def fetch_metadata_item_by_id(self, endpoint, uid):
        """
        Fetch a single metadata item (e.g., dataElement) by UID.
        """
        # Supported endpoints
        allowed_endpoints = {'dataElements', 'dataSets', 'validationRuleGroups', 'categoryOptionCombos', 'dataElementGroups'}
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
    def fetch_data_elements(self, query=None):
        return self.fetch_metadata_list('dataElements', 'dataElements', query)

    def fetch_data_sets(self, query=None, ):
        return self.fetch_metadata_list('dataSets', 'dataSets', query)

    def fetch_validation_rule_groups(self, query=None):
        return self.fetch_metadata_list('validationRuleGroups', 'validationRuleGroups', query)

    def fetch_data_element_groups(self, query=None):
        return self.fetch_metadata_list('dataElementGroups', 'dataElementGroups', query)

    def fetch_data_element_by_id(self, uid):
        return self.fetch_metadata_item_by_id('dataElements', uid)

    def fetch_data_element_group_by_id(self, uid):
        return self.fetch_metadata_item_by_id('dataElementGroups', uid)

    def fetch_dataset_by_id(self, uid):
        return self.fetch_metadata_item_by_id('dataSets', uid)

    def fetch_validation_rule_group_by_id(self, uid):
        return self.fetch_metadata_item_by_id('validationRuleGroups', uid)

    def fetch_category_option_combo_by_id(self, uid):
        return self.fetch_metadata_item_by_id('categoryOptionCombos', uid)

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


def generate_uid():
    return None