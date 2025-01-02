import argparse
from datetime import datetime
import json
import urllib3
import asyncio
import aiohttp
import logging
import lib.periodUtils as periodUtils
import lib.ValidationMonitorConfigReader as ConfigReader


class ValidationRuleGroupMonitor:
    def __init__(self, config_path):
        self.validation_rules = []
        self.config_reader = ConfigReader.ValidationMonitorConfigReader(config_path)

        self.config = self.config_reader.get_config()
        self.base_url = self.config_reader.base_url
        self.d2_token = self.config_reader.d2_token
        self.default_coc = self.config_reader.default_coc
        self.max_concurrent_requests = self.config_reader.max_concurrent_requests
        self.decimal_places = self.config_reader.decimal_places
        self.request_headers = {
            'Authorization': f'ApiToken {self.d2_token}',
            'Content-Type': 'application/json'
        }
        self.http = urllib3.PoolManager()
        self.validation_rule_group_count = self.get_validation_rule_group_count()

        self.logging_level = self.config.get("logging_level", "INFO")
        self.log_file = self.config.get("log_file", "validation_rule_monitor.log")

        logging.basicConfig(filename=self.log_file, level=self.logging_level,
                            format='%(asctime)s - %(levelname)s - %(message)s')

        self.periodUtils = periodUtils.Dhis2PeriodUtils()

    def get_organisation_units_at_level(self, level):
        url = f'{self.base_url}/api/organisationUnits.json?filter=level:eq:{level}&fields=id&paging=false'
        response = self.http.request('GET', url, headers=self.request_headers)
        response_data = json.loads(response.data.decode('utf-8'))
        ous = tuple(ou['id'] for ou in response_data['organisationUnits'])
        return ous

    def get_validation_rule_group_count(self):
        url = f'{self.base_url}/api/validationRuleGroups?fields=id,validationRules&paging=false'
        response = self.http.request('GET', url, headers=self.request_headers)
        vrgs = json.loads(response.data.decode('utf-8'))['validationRuleGroups']
        return {vrg['id']: len(vrg['validationRules']) for vrg in vrgs}

    def get_dataset_metadata(self, dataset_id):
        url = f'{self.base_url}/api/dataSets/{dataset_id}.json?fields=id,name,organisationUnits[id],periodType'
        response = self.http.request('GET', url, headers=self.request_headers)
        response_data = json.loads(response.data.decode('utf-8'))
        return response_data

    def get_validation_rules_in_dataset(self, dataset_id):
        url = f'{self.base_url}/api/validationRules.json?dataSet={dataset_id}&paging=false'
        response = self.http.request('GET', url, headers=self.request_headers)
        response_data = json.loads(response.data.decode('utf-8'))
        return tuple(vr['id'] for vr in response_data['validationRules'])

    async def fetch_dataset_validations_async(self, session, stage, periods, max_concurrent_requests):
        dataset = stage['dataset']
        ous = self.get_organisation_units_at_level(stage['level'])
        validation_rules = self.get_validation_rules_in_dataset(dataset)
        tasks = []
        semaphore = asyncio.Semaphore(max_concurrent_requests)
        for ou in ous:
            for period in periods:
                tasks.append(
                    self.fetch_dataset_validation_async(session, dataset, period, ou, validation_rules, semaphore))
        responses = await asyncio.gather(*tasks)
        responses = [response for response in responses if response is not None]

        org_units = set()
        for response in responses:
            org_units.add(response['organisationUnit'])
        # Sum the number of violations for each organisation unit across periods
        data_values = []
        for ou in org_units:
            total_violations = sum(
                response['violations'] for response in responses if response['organisationUnit'] == ou)
            data_values.append({
                'dataElement': stage['destination_data_element'],
                'orgUnit': ou,
                'categoryOptionCombo': self.default_coc,
                'value': total_violations
            })
        return data_values

    async def fetch_dataset_validation_async(self, session, dataset, period, ou, destination_de, semaphore):
        async with semaphore:
            url = f'{self.base_url}/api/validation/dataSet/{dataset}?pe={period}&ou={ou}'
            try:
                async with session.get(url, headers=self.request_headers) as response:
                    response_data = await response.json()
                    return {"organisationUnit": ou, "period": period, "dataElement": destination_de,
                            "violations": len(response_data['validationRuleViolations'])}
            except aiohttp.ClientError as e:
                logging.error(f"Request failed for dataset {dataset}, period {period}, org unit {ou}: {e}")
                return None

    async def trigger_validation_rule_analysis(self, session, vrg, ou, start_date, end_date):
        url = f'{self.base_url}/api/dataAnalysis/validationRules'
        body = {
            'notification': False,
            'persist': False,
            'ou': ou,
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'vrg': vrg
        }
        async with session.post(url, json=body) as response:
            return await response.json()

    def transform_validation_rule_response_to_datavalue(self, de, ou, value):
        return {
            'dataElement': de,
            'orgUnit': ou,
            'categoryOptionCombo': self.default_coc,
            'value': value
        }

    async def fetch_validation_rule_analysis_async(self, session, vrg, ou, start_date, number_of_periods, de,
                                                   semaphore):
        async with semaphore:
            response_data = await self.trigger_validation_rule_analysis(session, vrg, ou, start_date, datetime.now())
            rules_in_group = self.validation_rule_group_count[vrg]
            validation_rule_violation_count = len(response_data)
            validation_ratio = round(validation_rule_violation_count / (rules_in_group * number_of_periods) * 100,
                                     self.decimal_places)
            data_value = self.transform_validation_rule_response_to_datavalue(de, ou, validation_ratio)
            return data_value

    async def create_and_post_data_value_set(self, session, validation_rule_values):
        today = datetime.now()
        data_value_set = {'period': today.strftime("%Y%m%d"), 'dataValues': validation_rule_values}
        url = f'{self.base_url}/api/dataValueSets'
        async with session.post(url, json=data_value_set, headers=self.request_headers) as response:
            response = await response.json()
            return response

    async def run_validation_rule_group_stage_async(self, session, stage, max_concurrent_requests=10):
        number_of_periods = int(stage['duration'].split(' ')[0])
        print(f'Running stage {stage["name"]} for {number_of_periods} periods')
        start_date = self.periodUtils.get_start_date_from_today(stage['duration'])
        ous = self.get_organisation_units_at_level(stage['level'])
        vrgs = tuple(stage['validation_rule_groups'].split(','))
        semaphore = asyncio.Semaphore(max_concurrent_requests)
        tasks = []
        for ou in ous:
            for vrg in vrgs:
                de = stage['destination_data_element']
                tasks.append(
                    self.fetch_validation_rule_analysis_async(session, vrg, ou, start_date, number_of_periods, de,
                                                              semaphore))
        validation_rule_values = await asyncio.gather(*tasks)
        import_summary = await self.create_and_post_data_value_set(session, validation_rule_values)
        return import_summary

    async def run_all_stages_async(self, max_concurrent_requests=10):
        async with aiohttp.ClientSession(headers=self.request_headers) as session:
            logging.info(f"Running all stages with max concurrent requests {max_concurrent_requests}")
            clock_start = datetime.now()
            for stage in self.config['stages']:
                try:
                    logging.info(f"Running stage {stage['name']}")
                    if 'validation_rule_groups' in stage:
                        import_summary = await self.run_validation_rule_group_stage_async(session, stage,
                                                                                          max_concurrent_requests)
                        self.parse_import_summary(import_summary, stage['name'])
                    if 'dataset' in stage:
                        dataset_metadata = self.get_dataset_metadata(stage['dataset'])

                        current_period = self.periodUtils. \
                            get_current_period(period_type=dataset_metadata.get('periodType'))

                        periods = self.periodUtils. \
                            get_previous_periods(current_period,
                                                 dataset_metadata.get('periodType'),
                                                 stage['previous_periods'])

                        print(f"Running dataset stage {stage['name']} for {stage['previous_periods']} previous periods")
                        validation_rule_values = await self.fetch_dataset_validations_async(session,
                                                                                            stage,
                                                                                            periods,
                                                                                            max_concurrent_requests)

                        import_summary = await self.create_and_post_data_value_set(session, validation_rule_values)
                        self.parse_import_summary(import_summary, stage['name'])
                except Exception as e:
                    print(f"Error running stage {stage['name']}: {e}")
            logging.info("All stages completed")
            clock_end = datetime.now()
            logging.info(f"Process took: {clock_end - clock_start}")

    @staticmethod
    def parse_import_summary(import_summary, stage_name):
        if import_summary.get('status') == 'OK':
            logging.info(f"Stage {stage_name} completed successfully")
            response_data = import_summary.get('response', {})
            import_count = response_data.get('importCount', {})
            imported = import_count.get('imported', 0)
            updated = import_count.get('updated', 0)
            ignored = import_count.get('ignored', 0)
            deleted = import_count.get('deleted', 0)
            logging.info(f"Imported: {imported}, Updated: {updated}, Ignored: {ignored}, Deleted: {deleted}")
        else:
            logging.error(f"Error running stage {stage_name}")
            logging.error(import_summary)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Monitor validation rules')
    parser.add_argument('--config', help='Path to configuration file')
    args = parser.parse_args()

    monitor = ValidationRuleGroupMonitor(args.config)
    asyncio.run(monitor.run_all_stages_async(max_concurrent_requests=10))
