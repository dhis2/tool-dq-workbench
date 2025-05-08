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
            ous = await self.get_organisation_units_at_level(stage['level'], session)

        vrgs = tuple(params['validation_rule_groups'].split(','))
        max_results = params.get('max_results', self.config['server'].get('max_results', 500))
        data_element = params['destination_data_element']

        tasks = [
            self._fetch_validation_rule_analysis_async(
                session, vrg, ou, start_date, data_element, max_results, semaphore
            )
            for ou in ous for vrg in vrgs
        ]

        results_nested = await asyncio.gather(*tasks)
        return [item for sublist in results_nested for item in sublist]

    async def _fetch_validation_rule_analysis_async(self, session, vrg, ou, start_date, data_element, max_results, semaphore):
        async with semaphore:
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

            async with session.post(url, json=body) as response:
                response_data = await response.json()

        # Count violations by (orgUnit, period)
        violations = {}
        for result in response_data:
            key = (result['organisationUnitId'], result['periodId'])
            violations[key] = violations.get(key, 0) + 1

        return [{
            'dataElement': data_element,
            'orgUnit': ou_id,
            'period': period_id,
            'categoryOptionCombo': self.default_coc,
            'value': count
        } for (ou_id, period_id), count in violations.items()]
