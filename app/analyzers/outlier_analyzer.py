import asyncio
import logging
from datetime import datetime
from app.analyzers.stage_analyzer import StageAnalyzer

class OutlierAnalyzer(StageAnalyzer):
    def __init__(self, config, base_url, headers):
        super().__init__(config, base_url, headers)

    async def run_stage(self, stage, session, semaphore):
        try:
            logging.info(f"Running outlier stage '{stage['name']}'")

            start_date = self.get_start_date(stage)
            end_date = datetime.now()
            params = stage['params']

            organisation_unit = stage.get('organisation_unit')
            if isinstance(organisation_unit, list):
                ous = organisation_unit
            else:
                ous = await self.get_organisation_units_at_level(stage['level'], session)

            max_results = params.get('max_results', self.config['server'].get('max_results', 500))

            query_common = {
                'outlier_dataset': params['dataset'],
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'data_start_date': params.get('data_start_date'),
                'data_end_date': params.get('data_end_date'),
                'algorithm': params['algorithm'],
                'max_results': max_results,
                'threshold': params.get('threshold', 0),
                'destination_data_element': params['destination_data_element'],
                'lower_bound': params.get('lower_bound', 0)
            }

            tasks = [
                self._run_outlier_dataset_stage_async(session, {**query_common, 'ou': ou}, semaphore)
                for ou in ous
            ]

            results_nested = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            for i, result in enumerate(results_nested):
                if isinstance(result, Exception):
                    logging.error(f"Outlier detection failed for OU '{ous[i]}': {result}")
                    continue
                if isinstance(result, list):
                    results.extend(result)
                else:
                    logging.warning(f"Unexpected result for OU '{ous[i]}': {type(result)}")

            return results


        except Exception as e:
            logging.error(f"Error running outlier stage '{stage['name']}': {e}")
            return []

    async def _run_outlier_dataset_stage_async(self, session, params, semaphore):
        url = f"{self.base_url}/api/outlierDetection"
        parameters = [
            ('ds', params['outlier_dataset']),
            ('startDate', params['start_date']),
            ('endDate', params['end_date']),
            ('algorithm', params['algorithm']),
            ('maxResults', str(params['max_results'])),
            ('orderBy', 'MEAN_ABS_DEV'),
            ('threshold', str(params['threshold'])),
            ('ou', params['ou'])
        ]

        if params.get('data_start_date'):
            parameters['dataStartDate'] = params['data_start_date']
        if params.get('data_end_date'):
            parameters['dataEndDate'] = params['data_end_date']

        async with semaphore:
            logging.debug("Running outlier detection for organisation unit: %s for dataset %s", params['ou'],
                          params['outlier_dataset'])
            full_url = f"{url}?{'&'.join([f'{k}={v}' for k, v in parameters])}"
            logging.debug("Full URL: %s", full_url)
            async with session.get(url, params=parameters) as response:
                response.raise_for_status()
                outlier_json = await response.json()
                #Log any unexpected response that is not a 200
                if response.status != 200:
                    logging.error(f"Unexpected response status: {response.status}")
                    logging.error(f"Response content: {await response.text()}")

        return self._process_outlier_results(outlier_json, params['destination_data_element'], params['lower_bound'])

    def _process_outlier_results(self, results, destination_data_element, lower_bound):
        outliers_by_ou_and_period = {}

        for outlier in results.get('outlierValues', []):
            if float(outlier['value']) <= lower_bound:
                continue

            key = (outlier['ou'], outlier['pe'])
            outliers_by_ou_and_period[key] = outliers_by_ou_and_period.get(key, 0) + 1

        return [{
            'dataElement': destination_data_element,
            'orgUnit': ou,
            'period': period,
            'categoryOptionCombo': self.default_coc,
            'value': count
        } for (ou, period), count in outliers_by_ou_and_period.items()]
