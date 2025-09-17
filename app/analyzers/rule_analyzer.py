import asyncio
import logging
from datetime import datetime
from app.analyzers.stage_analyzer import StageAnalyzer

class ValidationRuleAnalyzer(StageAnalyzer):
    def __init__(self, config, base_url, headers):
        super().__init__(config, base_url, headers)
        
    async def data_values_urls_for_orgunits(self,stage,session, semaphore):
        urls = []
        start_date = self.get_start_date(stage)
        params = stage['params']
        data_element = params['destination_data_element']

        organisation_unit = stage.get('organisation_unit')
        if isinstance(organisation_unit, list):
            ous = organisation_unit
        else:
            ous = await self.get_organisation_units_at_level(params['level'], session, semaphore)

        params = {
            'dataElement': data_element,
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': datetime.now().strftime('%Y-%m-%d'),
            'children': 'true'}
        
        for ou in ous:
            params['orgUnit'] = ou
            query_string = '&'.join(f"{key}={value}" for key, value in params.items())
            url = f"{self.base_url}/api/dataValueSets.json?{query_string}"
            urls.append(url)
        return urls

    async def fetch_existing_datvalues(self,stage, session, semaphore):
        urls = await self.data_values_urls_for_orgunits(stage, session, semaphore)
        tasks = [
              self.fetch_datavalues_async(
                session, url, semaphore
            )
            for url in urls
        ]

        results = await asyncio.gather(*tasks)

        data_values = []
        for result in results:
            if isinstance(result, Exception):
                logging.error(f"Error fetching data values: {result}")
            elif isinstance(result, dict):
                data_values.extend(result.get('dataValues', []))
            else:
                logging.warning(f"Unexpected result type: {type(result)} from fetch_existing_datvalues")
        return data_values
    

    def classify_data(self, existing_data_values, calculated_data_values):
        existing_set = {
            (dv['dataElement'], dv['orgUnit'], dv['period'], dv.get('categoryOptionCombo', self.default_coc))
            for dv in existing_data_values
        }

        calculated_set = {
            (dv['dataElement'], dv['orgUnit'], dv['period'], dv.get('categoryOptionCombo', self.default_coc))
            for dv in calculated_data_values
        }

        to_delete = existing_set - calculated_set

        deletions = [
            {
                'dataElement': de,
                'orgUnit': ou,
                'period': period,
                'categoryOptionCombo': coc
            }
            for de, ou, period, coc in to_delete
        ]

        upserts = calculated_set - existing_set

        upsert_values = []
        delete_values = []
        #Filter the calculated set with the final upserts
        for upsert in upserts:
            for dv in calculated_data_values:
                if (dv['dataElement'], dv['orgUnit'], dv['period'], dv.get('categoryOptionCombo', self.default_coc)) == upsert:
                    upsert_values.append(dv)
                    break
        #Filter the existing set with the final deletions
        for deletion in to_delete:
            for dv in existing_data_values:
                if (dv['dataElement'], dv['orgUnit'], dv['period'], dv.get('categoryOptionCombo', self.default_coc)) == deletion:
                    delete_values.append(dv)
                    break
        #Return the original length of data
        calculated_data_length = len(calculated_data_values)
        return upsert_values, delete_values, calculated_data_length


    async def _fetch_validation_rule_analysis_async(self, session, vrg, ou, start_date, data_element, max_results,
                                                    semaphore):
        url = f'{self.base_url}/api/dataAnalysis/validationRules'
        body = {
            'notification': False,
            'persist': False,
            'ou': ou,
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': datetime.now().strftime('%Y-%m-%d'),
            'vrg': vrg,
            'maxResults': max_results
        }

        try:
            async with semaphore:
                logging.debug("Running validation rule analysis for ou '%s' and vrg '%s'", ou, vrg)
                logging.debug("Making POST request to URL: %s", url)
                logging.debug("Request body: %s", body)
                async with session.post(url, json=body) as response:
                    if response.status >= 400:
                        text = await response.text()
                        raise RuntimeError(f"{response.status} from DHIS2: {response.url} — {text.strip()}")
                    response_data = await response.json()
        except Exception as e:
            logging.error(f"Error fetching validation rule analysis: {e}")
            return e

        if not isinstance(response_data, list):
            logging.warning(f"Expected list from DHIS2 validation API but got {type(response_data)}: {response_data}")
            return []

        violations = {}
        for result in response_data:
            if 'organisationUnitId' not in result or 'periodId' not in result:
                logging.warning(f"Skipping malformed result: {result}")
                continue

            key = (result['organisationUnitId'], result['periodId'])
            violations[key] = violations.get(key, 0) + 1

        #Warn if the number of violations is exactly equal to the max_results
        if max_results == len(response_data):
            logging.error(f"Validation rule violations may be truncated. Consider to increase max_results")

        return [{
            'dataElement': data_element,
            'orgUnit': ou_id,
            'period': period_id,
            'categoryOptionCombo': self.default_coc,
            'value': count
        } for (ou_id, period_id), count in violations.items()]
    

    async def run_stage(self, stage, session, semaphore):
        logging.info(f"Running validation rule stage '{stage['name']}'")

        start_date = self.get_start_date(stage)
        params = stage['params']
        vrg = params['validation_rule_group']
        max_results = params.get('max_results', self.config['server'].get('max_results', 500))
        data_element = params['destination_data_element']

        organisation_unit = stage.get('organisation_unit')
        ous = []
        if isinstance(organisation_unit, list):
            ous = organisation_unit
        else:
            ous = await self.get_organisation_units_at_level(params['level'], session, semaphore)

        tasks = [
            self._fetch_validation_rule_analysis_async(
                session, vrg, ou, start_date, data_element, max_results, semaphore
            )
            for ou in ous
        ]

        results_nested = await asyncio.gather(*tasks)
        results = []
        errors = []

        for result in results_nested:
            if isinstance(result, Exception):
                logging.error(f"Validation rule analysis failed: {result}")
                errors.append(str(result))
            elif isinstance(result, list):
                results.extend(result)
            else:
                msg = f"Unexpected result in validation rule analysis: {type(result)}"
                logging.warning(msg)
                errors.append(msg)

        existing_data_values = await self.fetch_existing_datvalues(stage, session, semaphore)
        upserts, deletions, calculated_data_length = self.classify_data(existing_data_values, results)

        return {
            'dataValues': upserts,
            'deletions': deletions,
            'calculated_data_length' : calculated_data_length,
            'errors': errors
        }

