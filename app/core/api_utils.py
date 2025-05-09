import logging
import requests
from urllib.parse import urljoin

class Dhis2ApiUtils:
    def __init__(self, base_url, d2_token=None):
        self.base_url = base_url
        self.d2_token = d2_token
        self.request_headers = {
            'Authorization': f'ApiToken {self.d2_token}',
            'Content-Type': 'application/json'
        }

    async def get_organisation_units_at_level(self, level, session):
        url = f'{self.base_url}/api/organisationUnits.json?filter=level:eq:{level}&fields=id&paging=false'
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            return [ou['id'] for ou in data['organisationUnits']]

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
    def fetch_metadata_list(self, endpoint, key, query=None):
        """
        Fetch a list of metadata items (e.g., dataElements, dataSets, etc.)
        """
        url = f"{self.base_url}/api/{endpoint}.json?fields=id,name&paging=false"
        if query:
            url += f"&filter=name:ilike:{query}"
        logging.debug(f"Fetching metadata from URL: {url}")
        resp = requests.get(url, headers=self.request_headers)
        resp.raise_for_status()
        return resp.json().get(key, [])

    def fetch_metadata_item_by_id(self, endpoint, uid):
        """
        Fetch a single metadata item (e.g., dataElement) by UID.
        """
        # Supported endpoints
        allowed_endpoints = {'dataElements', 'dataSets', 'validationRuleGroups', 'categoryOptionCombos'}
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

    def fetch_data_sets(self, query=None):
        return self.fetch_metadata_list('dataSets', 'dataSets', query)

    def fetch_validation_rule_groups(self, query=None):
        return self.fetch_metadata_list('validationRuleGroups', 'validationRuleGroups', query)

    def fetch_data_element_by_id(self, uid):
        return self.fetch_metadata_item_by_id('dataElements', uid)

    def fetch_dataset_by_id(self, uid):
        return self.fetch_metadata_item_by_id('dataSets', uid)

    def fetch_validation_rule_group_by_id(self, uid):
        return self.fetch_metadata_item_by_id('validationRuleGroups', uid)

    def fetch_category_option_combo_by_id(self, uid):
        return self.fetch_metadata_item_by_id('categoryOptionCombos', uid)

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
        else:
            logging.error(f"Error posting data value set: {import_summary.get('status')}")
            logging.error(import_summary)
