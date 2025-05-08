import logging

import requests


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

    async def create_and_post_data_value_set(self,validation_rule_values, session):
        # Create the data value set
        datavalue_set = {
            'dataValues': validation_rule_values
        }
        url = f'{self.base_url}/api/dataValueSets'
        async with session.post(url, json= datavalue_set) as response:
            if response.status != 200:
                logging.error(f"Failed to post data value set: {response.status}")
                logging.error(await response.text())
                raise Exception(f"Failed to post data value set: {response.status}")
            resp = await response.json()
            return resp
    def fetch_data_elements(self, query=None):
        url = f"{self.base_url}/api/dataElements.json?fields=id,name&paging=false"
        if query:
            url += f"&filter=name:ilike:{query}"
        resp = requests.get(url, headers=self.request_headers)
        resp.raise_for_status()
        return resp.json().get("dataElements", [])

    def fetch_data_sets(self, query=None):
        url = f"{self.base_url}/api/dataSets.json?fields=id,name&paging=false"
        if query:
            url += f"&filter=name:ilike:{query}"
        resp = requests.get(url, headers=self.request_headers)
        resp.raise_for_status()
        return resp.json().get("dataSets", [])

    def fetch_validation_rule_groups(self, query=None):
        url = f"{self.base_url}/api/validationRuleGroups.json?fields=id,name&paging=false"
        if query:
            url += f"&filter=name:ilike:{query}"
        resp = requests.get(url, headers=self.request_headers)
        resp.raise_for_status()
        return resp.json().get("validationRuleGroups", [])

    def fetch_data_element_by_id(self, de_id):
        """
        Fetch a single data element by its UID from DHIS2.
        Returns a dict with 'id' and 'name'.
        """
        url = f"{self.base_url}/api/dataElements/{de_id}?fields=id,name"
        response = requests.get(url, headers=self.request_headers)
        response.raise_for_status()
        return response.json()

    def fetch_dataset_by_id(self, uid):
        url = f"{self.base_url}/api/dataSets/{uid}?fields=id,name"
        response = requests.get(url, headers=self.request_headers)
        response.raise_for_status()
        return response.json()

    def fetch_validation_rule_group_by_id(self, uid):
        url = f"{self.base_url}/api/validationRuleGroups/{uid}?fields=id,name"
        response = requests.get(url, headers=self.request_headers)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def parse_import_summary(import_summary):
        if import_summary.get('status') == 'OK':
            response = import_summary.get('response', {})
            import_count = response.get('importCount', {})
            imported = import_count.get('imported', 0)
            updated = import_count.get('updated', 0)
            ignored = import_count.get('ignored', 0)
            deleted = import_count.get('deleted', 0)
            logging.info(f"Imported: {imported}, Updated: {updated}, Ignored: {ignored}, Deleted: {deleted}")
        else:
            logging.error(f"Error posting data value set: {import_summary.get('status')}")
            logging.error(import_summary)
