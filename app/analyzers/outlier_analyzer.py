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

            query_params = {
                'outlier_dataset': params['dataset'],
                'organisation_unit': ous,
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

            return await self._run_outlier_dataset_stage_async(session, query_params, semaphore)

        except Exception as e:
            logging.error(f"Error running outlier stage '{stage['name']}': {e}")
            return []

    async def _run_outlier_dataset_stage_async(self, session, params, semaphore):
        url = f"{self.base_url}/api/outlierDetection"
        parameters = {
            'ds': params['outlier_dataset'],
            'ou': params['organisation_unit'],
            'startDate': params['start_date'],
            'endDate': params['end_date'],
            'algorithm': params['algorithm'],
            'maxResults': params['max_results'],
            'orderBy': 'MEAN_ABS_DEV',
            'threshold': params['threshold']
        }

        if params.get('data_start_date'):
            parameters['dataStartDate'] = params['data_start_date']
        if params.get('data_end_date'):
            parameters['dataEndDate'] = params['data_end_date']

        async with semaphore:
            async with session.get(url, params=parameters) as response:
                response.raise_for_status()
                outlier_json = await response.json()

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
