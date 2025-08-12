import asyncio
import logging
import math
import statistics
from collections import defaultdict

from requests import RequestException

from app.core.api_utils import Dhis2ApiUtils
from app.core.numeric_value_types import NumericValueType
from app.core.period_utils import Dhis2PeriodUtils
from app.minmax.min_max_results_tracker import ResultTracker
from app.minmax.min_max_statistics import (
    compute_statistical_bounds,
    select_method_for_median,
    past_values_max_bounds
)


class MinMaxFactory:
    MAX_INT_32 = 2_147_483_647

    def __init__(self, config):
        self.config = config
        self.base_url = config.get('server').get('base_url', '')
        self.d2_token = config.get('server').get('d2_token', '')
        self.default_coc = config['server'].get('default_coc', 'HllvX50cXC0')
        self.api_utils = Dhis2ApiUtils(self.base_url, self.d2_token)
        #Filter the stage in the min_max_stages
        self.stages = config.get('min_max_stages', [])
        self.period_utils = Dhis2PeriodUtils()
        self.result_tracker = ResultTracker()


    async def run_stage(self, stage: dict, session, semaphore):
        """
        Run a stage, including fetching data values,
        generating min/max values,
        and posting the results to the appropriate endpoint based on the server version.
        """
        prepared_stages = self.prepare_stage(stage)
        all_responses = []
        for prepared_stage in prepared_stages:
            grouped_values = await self.prepare_data_for_dataset(prepared_stage, semaphore, session)
            min_max_results = self.calculate_dataset_minmax_values(grouped_values, prepared_stage)
            payload = self.prepare_min_max_payload(min_max_results, prepared_stage['dataset_id'])

            #Decide to use bulk or legacy endpoint based on server version
            async with semaphore:
                server_version = await self.api_utils.get_server_version(session)
                upload_method = self._chose_min_max_upload_method(server_version)
                if upload_method == 'bulk':
                    logging.info("Using bulk endpoint for min/max values.")
                    response = await self.post_min_max_values_bulk(payload, session, semaphore)
                else:
                    logging.info("Using legacy endpoint for min/max values.")
                    response = await self.post_min_max_values(payload, session, semaphore)
            all_responses.append(response)
        return all_responses

    def calculate_dataset_minmax_values(self, grouped_data_values, prepared_stage):
        min_max_results = []
        for (ou_id, de_id, coc_id), values in grouped_data_values.items():
            try:
                min_max = self.calculate_min_max_value(ou_id, de_id, coc_id, values, prepared_stage)
                if min_max:
                    min_max_results.append(min_max)
            except Exception as e:
                logging.error(f"Error computing min/max for ({ou_id}, {de_id}, {coc_id}): {e}")
                logging.error(f"Values: {values}")
                logging.error(f"Minmax: {min_max}")
        logging.info(f"Computed {len(min_max_results)} min/max value sets.")
        return min_max_results

    async def prepare_data_for_dataset(self, prepared_stage, semaphore, session):
        logging.info(f"Processing dataset: {prepared_stage['dataset_id']}")
        data_values = await self.get_stage_data_values(prepared_stage, session, semaphore)
        logging.info(f"Fetched {len(data_values)} data values.")
        # Group data by (orgUnit, dataElement, categoryOptionCombo)
        grouped = defaultdict(list)
        for dv in data_values:
            key = (
                dv['orgUnit'],
                dv['dataElement'],
                dv.get('categoryOptionCombo', None)
            )
            value = dv.get("value")
            if value is None or value == "":
                logging.warning(f"Missing or empty value encountered in data value: {dv}")
                continue
            try:
                grouped[key].append(float(value))
            except (ValueError, TypeError):
                logging.warning(f"Invalid numeric value: {value} in {dv}")
        return grouped

    def _chose_min_max_upload_method(self, server_version):
        """
        Choose the upload method based on the server version.
        """
        if self.config.get('server', {}).get('min_max_bulk_api_disabled', False):
            logging.info("Use of bulk min max API is disabled in configuration.")
            return 'legacy'

        #The bulk API is available in DHIS2 2.41.5 and above
        server_v41_has_bulk_api = server_version and server_version['major'] >= 2 and server_version['minor'] == 41 and server_version['patch'] >= 5
        server_v42_has_bulk_api = server_version and server_version['major'] >= 2 and server_version['minor'] == 42 and server_version['patch'] > 0
        server_has_bulk_api = server_version and server_version['major'] >= 2 and server_version['minor'] >= 41
        if server_v41_has_bulk_api or  server_v42_has_bulk_api or server_has_bulk_api:
            return 'bulk'
        else:
            return 'legacy'

    @staticmethod
    def is_valid_min_max(item):

        try:
            return (
                    item
                    and isinstance(item["min"], int)
                    and isinstance(item["max"], int)
                    and abs(item["min"]) <= MinMaxFactory.MAX_INT_32
                    and abs(item["max"]) <= MinMaxFactory.MAX_INT_32
                    and item["min"] <= item["max"]
                    and item.get("dataElement")
                    and item.get("organisationUnit")
                    and item.get("optionCombo")
            )
        except (KeyError, TypeError):
            return False

    def prepare_min_max_payload(self, min_max_values, dataset_id):
        filtered_values = []
        for item in min_max_values:
            if self.is_valid_min_max(item):
                filtered_values.append(item)
            else:
                self.result_tracker.add_invalid_min_max()

        payload = {
            "dataSet": dataset_id,
            "values": [
                {
                    "dataElement": item["dataElement"],
                    "orgUnit": item["organisationUnit"],
                    "optionCombo": item["optionCombo"],
                    "minValue": item["min"],
                    "maxValue": item["max"]
                }
                for item in filtered_values
            ]
        }

        logging.info(f"Filtered {len(min_max_values) - len(filtered_values)} invalid min/max records.")
        logging.info(f"Prepared payload with {len(filtered_values)} values.")

        return payload

    async def post_min_max_values_bulk(self, payload, session, semaphore, chunk_size=100000):
        """
        Post the min/max values to the server in bulk in chunks to avoid payload size limits.
        """
        start_time = asyncio.get_event_loop().time()
        url = f'{self.base_url}/api/minMaxDataElements/upsert'
        values = payload["values"]
        total = len(values)
        data_set = payload["dataSet"]

        for i in range(0, total, chunk_size):
            chunk = values[i:i + chunk_size]
            chunk_payload = {
                "dataSet": data_set,
                "values": chunk
            }
            async with semaphore:
                async with session.post(url, json=chunk_payload) as response:
                    if response.status == 200:
                        resp = await response.json()
                        self.result_tracker.add_imported(resp.get("successful", 0))
                        self.result_tracker.add_ignored(resp.get("ignored", 0))
                        logging.info(f"Successfully posted chunk {i // chunk_size + 1} with {len(chunk)} values.")
                    else:
                        raise RequestException(
                            f"Failed to post min/max values chunk {i // chunk_size + 1}: {response.status} - {await response.text()}"
                        )

        end_time = asyncio.get_event_loop().time()
        elapsed_time = end_time - start_time
        logging.info(f"All chunks posted in {elapsed_time:.2f} seconds.")

    async def post_min_max_values(self, payload, session, semaphore):
        """
        Post min/max values using the legacy endpoint (2.41 and below).
        """
        async with semaphore:
            tasks = []
            for item in payload['values']:
                data = {
                    "dataElement": item["dataElement"],
                    "orgUnit": item["orgUnit"],
                    "categoryOptionCombo": item["optionCombo"],
                    "minValue": item["minValue"],
                    "maxValue": item["maxValue"]
                }
                tasks.append(self._post_single_min_max_value(data, session))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful = sum(1 for r in results if r is True)
            ignored = sum(1 for r in results if isinstance(r, Exception))

            return {
                "successful": successful,
                "ignored": ignored,
                "message": f"Successfully posted {successful} minmax values using legacy API"
            }

    async def _post_single_min_max_value(self, data, session):
        """
        Post a single min/max value to the server.
        """
        url = f'{self.base_url}/api/dataEntry/minMaxValues'
        async with session.post(url, json=data) as response:
            status = response.status
            if status == 200:
                return True
            else:
                error_text = await response.text()
                logging.error(f"Failed to post min/max value: {status} - {error_text}")
                raise RequestException(f"Failed to post min/max value: {status} - {error_text}")


    def get_dataset_metadata(self, dataset):
        """
        Fetch metadata for a specific dataset.
        """
        fields = ['id', 'periodType', 'dataSetElements[dataElement[id,valueType]]']

        resp = self.api_utils.fetch_metadata_list(
            endpoint='dataSets',
            key='dataSets',
            filters=[f'id:eq:{dataset}'],
            fields=fields,
            extra_params={'paging': 'false'}
        )
        if not resp:
            raise ValueError(f"Dataset {dataset} not found in metadata.")
        elif len(resp) > 1:
            raise ValueError(f"Expected one dataset, but got multiple for ID {dataset}: {resp}")
        else:
            return resp[0]

    def prepare_stage(self, stage):
        prepared_stages = []

        filtered_data_elements = self._resolve_filtered_data_elements(stage)

        datasets = stage.get('datasets', [])

        for dataset in datasets:
            dataset_metadata = self.get_dataset_metadata(dataset)
            dataset_period_type = dataset_metadata.get('periodType')
            dataset_id = dataset_metadata.get('id')

            current_period = self.period_utils.get_current_period(dataset_period_type)
            periods = sorted(
                self.period_utils.get_previous_periods(
                    current_period,
                    dataset_period_type,
                    stage.get('previous_periods', 12)
                )
            )

            prepared_stages.append({
                'name': stage.get('name'),
                'dataset': dataset,
                'dataset_id': dataset_id,
                'dataset_metadata': dataset_metadata,
                'dataset_period_type': dataset_period_type,
                'periods': periods,
                'period_count': len(periods),
                'current_period': current_period,
                'start_date': self.period_utils.get_start_date_from_period(periods[0]),
                'end_date': self.period_utils.get_end_date_from_period(periods[-1]),
                'org_units': stage.get('org_units'),
                'filtered_data_elements': filtered_data_elements,
                'completeness_threshold': stage.get('completeness_threshold',
                                                    self.config.get("completeness_threshold", 0.1)),
                'groups': stage.get('groups'),
            })

        return prepared_stages

    def _resolve_filtered_data_elements(self, stage):
        data_element_groups = stage.get('data_element_groups') or []
        data_elements = stage.get('data_elements') or []

        if not data_element_groups and not data_elements:
            return []

        data_elements_filter = []

        for group in data_element_groups:
            group_metadata = self.api_utils.fetch_data_element_groups(
                fields="id,name,dataElements[id,valueType]",
                filters=[f'id:eq:{group}']
            )
            data_elements = group_metadata.get('dataElements', [])
            data_elements_filter.extend(
                [de['id'] for de in data_elements if de.get('valueType') in NumericValueType.list()]
            )

        for de in data_elements:
            data_elements_filter.append(de)
        # Remove duplicates
        return list(set(data_elements_filter))

    async def fetch_datavalues_for_orgunit(self, prepared_stage, org_unit, session, semaphore):
        """
        Fetch data values for a specific organisation unit within the given date range.
        """
        url = f'{self.base_url}/api/dataValueSets'

        params = {
            'dataSet': prepared_stage['dataset_metadata']['id'],
            'orgUnit': org_unit,
            'startDate': prepared_stage['start_date'].strftime("%Y-%m-%d"),
            'endDate': prepared_stage['end_date'].strftime("%Y-%m-%d"),
            'children': 'true'
        }
        from urllib.parse import urlencode
        full_url = f"{url}?{urlencode(params)}"
        logging.debug("Dispatching data values request to URL: %s", full_url)
        async with semaphore:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    resp = await response.json()
                    des_in_dataset = prepared_stage['dataset_metadata'].get('dataSetElements', [])
                    #Filter these to get the numeric data elements
                    numeric_des = [de for de in des_in_dataset if
                                   de.get('dataElement', {}).get('valueType') in NumericValueType.list()]
                    #Filter the data values to only include these numeric data elements
                    data_values = [
                        dv for dv in resp.get('dataValues', [])
                        if dv.get('dataElement') in [de['dataElement']['id'] for de in numeric_des]
                    ]
                    #Filter out the data elements which are part of the filtered data elements
                    if prepared_stage['filtered_data_elements']:
                        data_values = [
                            dv for dv in data_values
                            if dv.get('dataElement') in prepared_stage['filtered_data_elements']
                        ]
                    return {'dataValues': data_values}
                else:
                    raise RequestException(f"Failed to fetch data values: {response.status} - {await response.text()}")

    async def get_stage_data_values(self, prepared_stage, session, semaphore):

        tasks = [
            self.fetch_datavalues_for_orgunit(prepared_stage, org_unit, session, semaphore)
            for org_unit in prepared_stage['org_units']
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        data_values = []
        for result in results:
            if isinstance(result, Exception):
                logging.error(f"Error fetching data values: {result}")
            elif isinstance(result, dict):
                data_values.extend(result.get('dataValues', []))
            else:
                logging.warning(f"Unexpected result type: {type(result)} from get_datavalues_for_orgunit")
        return data_values


    async def fetch_existing_min_max_values(self, prepared_stage, session, semaphore, generated=False):
        """
        Fetch existing min/max values for the given stage.
        id,periodType,dataSetElements[dataElement[id,valueType]]',
        """
        des_in_dataset = self.dataset_metadata.get('dataSetElements', [])
        numeric_des = [de for de in des_in_dataset if
                       de.get('dataElement', {}).get('valueType') in NumericValueType.list()]
        url = f'{self.base_url}/api/minMaxDataElements?filter=dataElement.id:in:[', ','.join(
            [de['dataElement']['id'] for de in numeric_des]), ']'
        url = f"{url}&filter=source.id:in:[{','.join(prepared_stage.get('org_units', []))}]"
        url = f"{url}&filter=generated:eq:", str(generated).lower()
        #Skip paging
        url = f"{url}&paging=false"

        async with semaphore:
            async with session.get(url) as response:
                if response.status == 200:
                    resp = await response.json()
                    return resp.get('minMaxDataElements', [])
                else:
                    raise RequestException(
                        f"Failed to fetch existing min/max values: {response.status} - {await response.text()}")

    def calculate_min_max_value(self, ou_id, de_id, coc_id, values, stage):
        if not values:
            return None

        values = [v for v in values if isinstance(v, (int, float))]
        #Adjust numbers to be positive, as min/max values are always positive
        min_value = min(values)
        #Arbitrary small epsilon to avoid zero values which will lead to problems with Box/Cox
        epsilon = 1e-3
        if min_value <= 0:
            min_value_offset = abs(min_value) + epsilon
            values = [v + min_value_offset for v in values]
            logging.info(f"Adjusted values for DE {de_id} in OU {ou_id} to be positive: {values}")
        else:
            min_value_offset = 0
        periods_with_data = float(len(values))
        completeness_threshold = float(stage.get("completeness_threshold", self.config.get("completeness_threshold", 0.1)))
        period_count = float(stage.get("period_count"))

        required_periods = math.ceil(period_count * completeness_threshold)
        if periods_with_data < required_periods:
            self.result_tracker.add_missing()
            return None

        self.result_tracker.add_valid()
        median_val = statistics.median(values)

        method, threshold = select_method_for_median(stage.get("groups", []), median_val)

        if method == "CONSTANT":
            #Filter the groups which have method as CONSTANT
            constant_groups = [g for g in stage.get("groups", []) if g.get("method") == "CONSTANT"]
            #Chose the group whose limitMedian is the closest to the median value
            constant_group = min(constant_groups, key=lambda g: abs(g.get("limitMedian", float('inf')) - median_val), default=None)
            #Get the min and max constants from the group
            min_constant = constant_group.get("constantMin", None)
            max_constant = constant_group.get("constantMax", None)
            if not isinstance(min_constant, int) or not isinstance(max_constant, int):
                self.result_tracker.add_error()
                logging.error(f"Invalid constant values for DE {de_id} in OU {ou_id}: {min_constant}, {max_constant}")
                return None
            if min_constant >= max_constant:
                self.result_tracker.add_error()
                logging.error(f"Min constant is greater than or equal to max constant for DE {de_id} in OU {ou_id}: {min_constant} > {max_constant}")
                return None
            val_min = min_constant
            val_max = max_constant
            comment = "CONSTANT"
        else:
            val_min, val_max, comment = compute_statistical_bounds(values, method, threshold)

            if not math.isfinite(val_min) or not math.isfinite(val_max):
                self.result_tracker.add_fallback()
                val_max, val_min = past_values_max_bounds(values, 1.5)
                comment += " - Fallback to Prev max"

            #Need to offset back with the min_value adjustment
            val_max = math.ceil(val_max - min_value_offset)
            val_min = math.floor(val_min - min_value_offset)

        is_outlier = max(values) > val_max or min(values) < val_min
        if is_outlier:
            self.result_tracker.add_bound_warning()
            comment += " - Bounds may be too narrow (historical values exceed)"

        if val_max == val_min:
            self.result_tracker.add_error()
            logging.warning(f"Min and max are equal for DE {de_id} in OU {ou_id} with values: {values}")
            return None

        return {
            "min": val_min,
            "max": val_max,
            "generated": True,
            "dataElement": de_id,
            "organisationUnit": ou_id,
            "optionCombo": coc_id,
            "comment": comment,
        }


