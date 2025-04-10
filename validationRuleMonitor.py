from time import strftime, strptime

import yaml
import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import urllib3
import asyncio
import aiohttp
import logging
import lib.periodUtils as periodUtils

class ValidationRuleMonitor:
    def __init__(self, config_path):
        self.validation_rules = []
        self.config = {}

        with open(config_path, 'r') as stream:
            self.config = yaml.safe_load(stream)
        self.validate_config()
        self.base_url = self.config['server']['base_url']
        self.d2_token = self.config['server']['d2_token']
        self.default_coc = self.config['server']['default_coc']
        self.max_concurrent_requests = self.config['server'].get('max_concurrent_requests', 10)
        self.decimal_places = self.config['server'].get('decimal_places', 3)

        self.request_headers = {
            'Authorization': f'ApiToken {self.d2_token}',
            'Content-Type': 'application/json'
        }
        self.http = urllib3.PoolManager()
        self.validation_rule_group_count = self.get_validation_rule_group_count()

        self.logging_level = self.config['server'].get("logging_level", "INFO")
        self.log_file = self.config['server'].get("log_file", "validation_rule_monitor.log")

        logging.basicConfig(filename=self.log_file, level=self.logging_level,
                            format='%(asctime)s - %(levelname)s - %(message)s')


    def validate_config(self):
        if 'stages' not in self.config:
            raise ValueError("No stages defined in configuration")

        for stage in self.config['stages']:
            if 'name' not in stage:
                raise ValueError("Stage name not defined")
            if 'level' not in stage:
                raise ValueError("Organisation unit level not defined")
            if 'duration' not in stage:
                raise ValueError("Duration not defined")
            if 'validation_rule_groups' not in stage:
                raise ValueError("Validation rule groups not defined")
            if 'destination_data_element' not in stage:
                raise ValueError("Destination data element not defined")
    @staticmethod
    def get_start_date_from_today(duration_string):
        amount, unit = duration_string.split(' ')
        amount = int(amount)

        if amount is None or len(unit) == 0:
            raise ValueError("Invalid duration format")

        unit = unit.rstrip('s')
        supported_units = {'day': 'days', 'week': 'weeks', 'month': 'months', 'year': 'years'}

        if unit not in supported_units:
            raise ValueError("Invalid duration unit")

        delta = relativedelta(**{supported_units[unit]: amount})
        return datetime.now() - delta

    def get_organisation_units_at_level(self, level):
        url = f'{self.base_url}/api/organisationUnits.json?filter=level:eq:{level}&fields=id&paging=false'
        response = self.http.request('GET', url, headers=self.request_headers)
        response_data = json.loads(response.data.decode('utf-8'))
        return tuple(ou['id'] for ou in response_data['organisationUnits'])

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


    async def fetch_dataset_validations_async(self, session, dataset, periods, semaphore):
        dataset_metadata = self.get_dataset_metadata(dataset)
        ous = dataset_metadata['organisationUnits']
        validation_rules = self.get_validation_rules_in_dataset(dataset)
        validation_rule_count = len(validation_rules)
        tasks = []
        for ou in ous:
            for period in periods:
                tasks.append(self.fetch_dataset_validation_async(session, dataset, period, ou, validation_rules, semaphore))
        responses = await asyncio.gather(*tasks)

        datavalues = []
        for response in responses:
            response_data = json.loads(response)
            validation_ratio = round(len(response_data['validationRules']) / validation_rule_count * 100, self.decimal_places)
            # only create a data value if we have a value greater than 0
            if validation_ratio == 0:
                continue
            datavalue = {
                'organisationUnit': response_data['orgUnit'],
                'period': response_data['period'],
                'dataElement': response_data['destination_de'],
                'categoryOptionCombo': self.default_coc,
                'value': validation_ratio
            }
            datavalues.append(datavalue)
        dv_response = self.create_and_post_data_value_set(session, datavalues)
        return dv_response

    async def fetch_dataset_validation_async(self, session, dataset, period, ou, destination_de, semaphore):
        async with semaphore:
            url = f'{self.base_url}/api/dataValueSets?dataSet={dataset}&period={period}&orgUnit={ou["id"]}'
            async with session.get(url, headers=self.request_headers) as response:
                response_data = await response.json()
                return {"ou": ou["id"], "period": period, "destination_de" : destination_de, "response": response_data}

    async def trigger_validation_rule_analysis(self, session, vrg, ou, start_date, end_date, max_results=500):
        url = f'{self.base_url}/api/dataAnalysis/validationRules'
        body = {
            'notification': False,
            'persist': False,
            'ou': ou,
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'vrg': vrg,
            'maxResults': max_results
        }
        async with session.post(url, json=body) as response:
            return await response.json()

    def transform_validation_rule_response_to_datavalue(self, de,ou,value):
        return {
            'dataElement': de,
            'orgUnit': ou,
            'categoryOptionCombo': self.default_coc,
            'value': value
        }

    @staticmethod
    def process_validation_results(self, results, period):
        """Process validation results for a specific period"""
        violations_per_org_unit = {}
        for result in results:
            ou_id = result['organisationUnitId']
            if ou_id in violations_per_org_unit:
                violations_per_org_unit[ou_id] += 1
            else:
                violations_per_org_unit[ou_id] = 1

        # Create data values with period
        data_values = []
        for ou, count in violations_per_org_unit.items():
            data_value = {
                'period': period,
                'orgUnit': ou,
                'value': count
            }
            data_values.append(data_value)
        return data_values

    async def fetch_validation_rule_analysis_async(self, session, vrg, ou, start_date, number_of_periods, de,
                                                   max_results, semaphore):
        async with semaphore:
            response = await self.trigger_validation_rule_analysis(session, vrg, ou, start_date, datetime.now(),
                                                                   max_results)
            violations_per_org_unit_period = {}
            # Create a warning int the log if the number of results is greater than the max_results
            if len(response) > max_results:
                logging.warning(f"Number of results {len(response)} is greater than max_results {max_results} for VRG {vrg} and OU {ou}")
            # Process the response to count violations per org unit and period
            for result in response:
                ou_id = result['organisationUnitId']
                period_id = result['periodId']
                key = (ou_id, period_id)
                if key in violations_per_org_unit_period:
                    violations_per_org_unit_period[key] += 1
                else:
                    violations_per_org_unit_period[key] = 1

            data_values = []
            for (ou_id, period_id), count in violations_per_org_unit_period.items():
                data_value = {
                    'dataElement': de,
                    'orgUnit': ou_id,
                    'period': period_id,
                    'categoryOptionCombo': self.default_coc,
                    'value': count
                }
                data_values.append(data_value)
            return data_values

    async def create_and_post_data_value_set(self, session, validation_rule_values):
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

    async def run_validation_rule_group_stage_async(self, session, stage, semaphore):
        number_of_periods = int(stage['duration'].split(' ')[0])
        print(f'Running stage {stage["name"]} for {number_of_periods} periods')
        start_date = self.get_start_date_from_today(stage['duration'])
        ous = self.get_organisation_units_at_level(stage['level'])
        vrgs = tuple(stage['validation_rule_groups'].split(','))

        max_results = stage.get('max_results', 500)
        tasks = []
        for ou in ous:
            for vrg in vrgs:
                de = stage['destination_data_element']
                tasks.append(
                    self.fetch_validation_rule_analysis_async(session, vrg, ou, start_date, number_of_periods, de,
                                                              max_results,
                                                              semaphore))
        return await asyncio.gather(*tasks)


    async def run_stage(self, session, stage, semaphore):
        try:
            logging.info(f"Running stage {stage['name']}")
            if 'validation_rule_groups' in stage:
                validation_rule_values = await self.run_validation_rule_group_stage_async(session, stage, semaphore)
                return validation_rule_values

            # if 'datasets' in stage:
            #     start_date = datetime.now()
            #     dataset_metadata = self.get_dataset_metadata(stage['dataset'])
            #     periods = periodUtils.get_previous_periods(start_date, dataset_metadata.get('periodType'),
            #                                                stage['duration'])
            #     import_summary = await self.fetch_dataset_validations_async(session, stage['dataset'], periods,
            #                                                                 max_concurrent_requests)
            #     self.parse_import_summary(import_summary, stage['name'])

        except Exception as e:
            logging.error(f"Error running stage {stage['name']}: {e}")


    async def run_stage_with_semaphore(self, semaphore, session, stage):
        return await self.run_stage(session, stage, semaphore)

    async def run_all_stages(self):
        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async with aiohttp.ClientSession(headers=self.request_headers) as session:
            logging.info(f"Running all stages with max concurrent requests {self.max_concurrent_requests}")
            clock_start = datetime.now()

            # Build stage tasks with concurrency control
            tasks = [
                self.run_stage_with_semaphore(semaphore = semaphore, session=session, stage=stage)
                for stage in self.config['stages']
            ]

            # Run them concurrently, limited by the semaphore
            validation_rule_values_nested = await asyncio.gather(*tasks)
            validation_rule_values = [
                item for stage_results in validation_rule_values_nested for sublist in stage_results for item in sublist
            ]
            logging.info(f"Posting {len(validation_rule_values)} data values")
            dvs_post_result = await self.create_and_post_data_value_set(session, validation_rule_values)
            self.parse_import_summary(dvs_post_result)
            logging.info("All stages completed")
            clock_end = datetime.now()
            logging.info(f"Process took: {clock_end - clock_start}")

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

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Monitor validation rules')
    parser.add_argument('--config', help='Path to configuration file')
    args = parser.parse_args()

    monitor = ValidationRuleMonitor(args.config)
    asyncio.run(monitor.run_all_stages())