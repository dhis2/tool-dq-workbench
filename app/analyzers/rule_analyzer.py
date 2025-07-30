import asyncio
import logging
from datetime import datetime
from app.analyzers.stage_analyzer import StageAnalyzer

class ValidationRuleAnalyzer(StageAnalyzer):
    def __init__(self, config, base_url, headers):
        super().__init__(config, base_url, headers)

    async def run_stage(self, stage, session, semaphore):
        logging.info(f"Running validation rule stage '{stage['name']}'")

        start_date = self.get_start_date(stage)
        params = stage['params']

        organisation_unit = stage.get('organisation_unit')
        if isinstance(organisation_unit, list):
            ous = organisation_unit
        else:
            ous = await self.get_organisation_units_at_level(stage['level'], session, semaphore)

        vrg = params['validation_rule_group']
        max_results = params.get('max_results', self.config['server'].get('max_results', 500))
        data_element = params['destination_data_element']

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

        return {
            'data_values': results,
            'errors': errors
        }

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

        # ✅ Safe-check and normalize
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

        return [{
            'dataElement': data_element,
            'orgUnit': ou_id,
            'period': period_id,
            'categoryOptionCombo': self.default_coc,
            'value': count
        } for (ou_id, period_id), count in violations.items()]

