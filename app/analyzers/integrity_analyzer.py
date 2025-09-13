import asyncio

import logging
from app.core.api_utils import Dhis2ApiUtils
from urllib.parse import urlencode
from app.core.period_utils import Dhis2PeriodUtils

import requests.exceptions

from app.analyzers.stage_analyzer import StageAnalyzer

class IntegrityCheckAnalyzer(StageAnalyzer):
    def __init__(self, config, base_url, headers):
        super().__init__(config, base_url, headers)

        #Define a period utils instance for this class
        self.api_utils = Dhis2ApiUtils(base_url, d2_token=self.d2_token)
        self.period_utils = Dhis2PeriodUtils()

    async def run_stage(self, stage, session, semaphore):
        try:
            logging.info(f"Running metadata integrity stage '{stage['name']}'")
            #Start with grabbing the data element group
            de_group = stage.get('params', {}).get('monitoring_group')
            data_element_map = await self.fetch_data_elements_to_monitor(session, {'monitoring_group': de_group}, semaphore)
            #Append this map to the stage params
            stage['params']['data_element_map'] = data_element_map
            #Get the current period based on the period type on the config
            period_type = stage.get('params', {}).get('period_type')
            if period_type is None:
                raise ValueError("Period type is not specified in the stage params")
            current_period = self.period_utils.get_current_period(period_type)
            print("Current period: ", current_period)
            #Append to the params
            stage['params']['current_period'] = current_period
            #Get the level one orgunit
            orgunit = await  self.api_utils.get_organisation_units_at_level(1,session, semaphore)
            #Append this to the params
            if len(orgunit) == 0:
                raise ValueError("No level one organisation unit found")
            stage['params']['orgunit'] = orgunit[0]

            results = await self._fetch_summary_results_async(session, stage, semaphore)
            data_values =  self.process_results(results, stage)
            return {
                'dataValues': data_values,
                'errors': []
            }

        except Exception as e:
            logging.error(f"Error running outlier stage '{stage['name']}': {e}")
            return []

    async def fetch_data_elements_to_monitor(self, session, params, semaphore):
        """
        Fetches data elements from the specified group and maps them by normalized code (without 'MI_' prefix).
        """
        url = f'{self.base_url}/api/dataElementGroups'

        if 'monitoring_group' in params:
            fields_to_get = "dataElements[id,code]"
            url = f'{url}/{params["monitoring_group"]}?fields={fields_to_get}'

        async with semaphore:
            async with session.get(url) as response:
                if response.status == 200:
                    payload = await response.json()
                    raw_elements = payload.get("dataElements", [])

                    # Normalize and include both codes
                    normalized_map = {}
                    for de in raw_elements:
                        original_code = de.get("code", "")
                        if original_code.startswith("MI_"):
                            check_code = original_code[3:]  # Strip 'MI_'
                            normalized_map[check_code] = {
                                "id": de["id"],
                                "de_code": original_code,
                                "check_code": check_code,
                                "name": de.get("name", "")
                            }
                    return normalized_map
                else:
                    raise requests.exceptions.RequestException(
                        f"Failed to fetch data elements to monitor: {response.status}")

    async def _trigger_metadata_integrity_summaries_async(self, session, stage, semaphore):
        # POST /api/dataIntegrity/summary?checks=<name1>,<name2>
        params = stage.get('params', {}).get("data_element_map", {}).keys()
        url = f'{self.base_url}/api/dataIntegrity/summary'
        if 'checks' in params:
            query = urlencode({'checks': ','.join(params['checks'])})
            url = f'{url}?{query}'

        async with semaphore:
            async with session.post(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise requests.exceptions.RequestException(f"Failed to trigger metadata integrity summaries: {response.status}")

    async def _poll_running_summaries_async(self, session,semaphore):
        # GET /api/dataIntegrity/summary/running
        url = f'{self.base_url}/api/dataIntegrity/summary/running'
        async with semaphore:
            async with session.get(url) as response:
                if response.status == 200:
                   response = await response.json()
                   return response
                else:
                    raise requests.exceptions.RequestException(f"Failed to poll running summaries: {response.status}")

    async def _fetch_completed_summaries_async(self, session, stage, semaphore):
        # GET /api/dataIntegrity/summary/completed
        params = stage.get('params', {}).get("data_element_map", {}).keys()
        url = f'{self.base_url}/api/dataIntegrity/summary'
        if params is not None:
            query = urlencode({'checks': ','.join(params)})
            url = f'{url}?{query}'
        async with semaphore:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise requests.exceptions.RequestException(f"Failed to fetch completed summaries: {response.status}")

    async def _fetch_summary_results_async(self, session, stage, semaphore):
        await self._trigger_metadata_integrity_summaries_async(session, stage, semaphore)
        await asyncio.sleep(5)
        running = await self._poll_running_summaries_async(session, semaphore)
        timeout = 600
        while running and timeout > 0:
            await asyncio.sleep(5)
            running = await self._poll_running_summaries_async(session, semaphore)
            timeout -= 5
        results =  await self._fetch_completed_summaries_async(session, stage, semaphore)
        return results

    @staticmethod
    def transform_integrity_check_to_data_value(result, dataelement_uid, period, orgunit):
        if result is None:
            return None
        #Attempt to parse to integer
        value = result["count"]
        if value is None or value == "":
            logging.warning(f"Result was blank for {dataelement_uid} ")
            return None
        try:
            value_int = int(value)
            if value_int < 0:
                logging.error(f"Value: {value}) is less than 0 for {dataelement_uid}")
                return None
        except ValueError:
            logging.error(f"Failed to convert {value} to int: {value} for {dataelement_uid}")
            return None

        data = {
            "dataElement": dataelement_uid,
            "period": period,
            "orgUnit": orgunit,
            "value": result["count"]
        }
        return data

    def process_results(self, results, stage):
        current_period = stage.get('params', {}).get('current_period')
        orgunit = stage.get('params', {}).get('orgunit')
        data_element_map = stage.get('params', {}).get('data_element_map')
        data_values = []
        print("Results: ", results)
        print("Data element map: ", stage.get("params", {}).get("data_element_map"))
        for _, v in results.items():
            check_code = v.get("code")
            data_element = data_element_map.get(check_code)
            if data_element is None:
                logging.warning(f"Data element not found for check code: {check_code}")
                continue
            data_element_uid = data_element.get('id')
            data_value = self.transform_integrity_check_to_data_value(v, data_element_uid, current_period, orgunit)
            if data_value is not None:
                data_values.append(data_value)
        return data_values


    def _fetch_existing_integrity_des(self):
        filters = ["name:$like:[MI]"]
        return self.api_utils.fetch_data_elements(filters=filters, fields=["id", "name", "code"])


    def get_integrity_checks_no_data_elements(self):
        checks = self.api_utils.get_metadata_integrity_checks()
        #Exclude any slow checks
        checks = [check for check in checks if not check["isSlow"]]
        des = self._fetch_existing_integrity_des()
        #Remove the MI_ prefix from each code
        for de in des:
            this_code = de["code"][3:]
            for check in checks:
                if check["code"] == this_code:
                    checks.remove(check)
        return checks
