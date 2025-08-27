import asyncio
import logging
from datetime import datetime
from app.core.period_utils import Dhis2PeriodUtils
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
                ous = await self.get_organisation_units_at_level(params['level'], session, semaphore)

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
            #Optionally add date offsets if provided
            if 'start_date_offset' in params:
                query_common['start_date_offset'] = params['start_date_offset']
            if 'end_date_offset' in params:
                query_common['end_date_offset'] = params['end_date_offset']


            tasks = [
                self._run_outlier_dataset_stage_async(session, {**query_common, 'ou': ou}, semaphore)
                for ou in ous
            ]

            results_nested = await asyncio.gather(*tasks, return_exceptions=True)
            results = []
            errors = []

            for i, result in enumerate(results_nested):
                ou = ous[i]
                if isinstance(result, Exception):
                    msg = f"Outlier detection failed for OU '{ou}': {str(result)}"
                    logging.error(msg)
                    errors.append(msg)
                elif isinstance(result, list):
                    results.extend(result)
                else:
                    msg = f"Unexpected result type for OU '{ou}': {type(result)}"
                    logging.warning(msg)
                    errors.append(msg)
            return {
                'dataValues': results,
                'errors': errors
            }

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

        if params.get('start_date_offset'):
            start_date = Dhis2PeriodUtils.get_start_date_from_today(params.get('start_date_offset'))
            parameters.append(('dataStartDate', start_date.strftime('%Y-%m-%d')))
        if params.get('end_date_offset'):
            end_date = Dhis2PeriodUtils.get_start_date_from_today(params.get('end_date_offset'))
            parameters.append(('dataEndDate', end_date.strftime('%Y-%m-%d')))

        try:
            async with semaphore:
                async with session.get(url, params=parameters) as response:
                    if response.status >= 400:
                        # Don't raise — just return detailed error
                        text = await response.text()
                        raise RuntimeError(f"{response.status} from DHIS2: {response.url} — {text.strip()}")
                    outlier_json = await response.json()

            return self._process_outlier_results(outlier_json, params['destination_data_element'],
                                                 params['lower_bound'])

        except Exception as e:
            return e

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
