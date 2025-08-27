import asyncio
import logging
import math
import random
import secrets
import statistics
from collections import defaultdict
from typing import List, Iterable

import pandas as pd
from requests import RequestException

from app.core.api_utils import Dhis2ApiUtils
from app.core.numeric_value_types import NumericValueType
from app.core.period_utils import Dhis2PeriodUtils
from app.minmax.min_max_results_tracker import ResultTracker
from app.minmax.min_max_record import MinMaxRecord
from app.minmax.min_max_statistics import (
    compute_statistical_bounds,
    select_method_for_median,
    past_values_max_bounds,
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
        #Check the user can even upload min/max values
        user_can_upload = self._check_can_upload_minmax()
        if not user_can_upload:
            raise PermissionError("User does not have permission to upload min/max values. Please check the user permissions.")

        for prepared_stage in prepared_stages:
            data_values = await self.fetch_data_for_dataset(prepared_stage, semaphore, session)
            grouped_values = self.group_data_for_dataset(data_values)
            min_max_results = self.calculate_dataset_minmax_values(grouped_values, prepared_stage)
            imputed_results = self.impute_missing_minmmax_values(prepared_stage, min_max_results)
            payload = self.prepare_min_max_payload(imputed_results, prepared_stage['dataset_id'])
            #GH

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
        logging.info(f"Computed {len(min_max_results)} min/max value sets.")
        return min_max_results

    async def fetch_data_for_dataset(self, prepared_stage, semaphore, session):
        # normalize input: accept dict or 1-item list[dict]
        if isinstance(prepared_stage, list):
            if len(prepared_stage) == 1 and isinstance(prepared_stage[0], dict):
                prepared_stage = prepared_stage[0]
            else:
                raise TypeError(
                    f"Expected dict or single-item list of dicts for prepared_stage, got: {type(prepared_stage)} ({prepared_stage!r})"
                )

        logging.info(f"Processing dataset: {prepared_stage['dataset_id']}")
        data_values = await self.get_stage_data_values(prepared_stage, session, semaphore)
        logging.info(f"Fetched {len(data_values)} data values.")
        return data_values

    @staticmethod
    def group_data_for_dataset(data_values):
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
    def is_valid_min_max(item: "MinMaxRecord") -> bool:
        # Only accept the dataclass
        if not isinstance(item, MinMaxRecord):
            return False

        # Must have identifiers
        if not (item.dataElement and item.organisationUnit and item.optionCombo):
            return False

        # min/max must be ints and within bounds and ordered
        if not (isinstance(item.min, int) and isinstance(item.max, int)):
            return False

        if abs(item.min) > MinMaxFactory.MAX_INT_32 or abs(item.max) > MinMaxFactory.MAX_INT_32:
            return False

        if item.min > item.max:
            return False

        return True

    def prepare_min_max_payload(self, min_max_values: Iterable[MinMaxRecord], dataset_id: str) -> dict:
        filtered: List[MinMaxRecord] = []

        for rec in min_max_values:
            if not isinstance(rec, MinMaxRecord):
                logging.warning("Non-MinMaxRecord encountered: %r", type(rec))
                self.result_tracker.add_invalid_min_max()
                continue

            if self.is_valid_min_max(rec):
                filtered.append(rec)
            else:
                self.result_tracker.add_invalid_min_max()

        values = [
            {
                "dataElement": r.dataElement,
                "orgUnit": r.organisationUnit,
                "optionCombo": r.optionCombo,
                "minValue": int(r.min),
                "maxValue": int(r.max),
            }
            for r in filtered
        ]

        payload = {"dataSet": dataset_id, "values": values}

        logging.info("Filtered %d invalid min/max records.", len(list(min_max_values)) - len(filtered))
        logging.info("Prepared payload with %d values.", len(values))

        return payload



    async def _post_chunk(self, url, chunk_payload, session, semaphore, index: int,
                          max_retries: int = 3, backoff_base: float = 0.5):

        OK_STATUSES = {200, 201}
        RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}

        """
        Post one chunk with bounded concurrency and simple exponential backoff.
        Returns (successful, ignored).
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                async with semaphore:
                    async with session.post(url, json=chunk_payload) as response:
                        if response.status in OK_STATUSES:
                            # Body may be JSON or empty
                            try:
                                resp = await response.json()
                            except Exception:
                                resp = {}
                            successful = resp.get("successful", len(chunk_payload["values"]))
                            ignored = resp.get("ignored", 0)
                            logging.info(
                                f"Chunk {index} OK (attempt {attempt}) with {len(chunk_payload['values'])} values.")
                            return successful, ignored

                        # Retry on transient/rate-limit statuses
                        text = await response.text()
                        if response.status in RETRYABLE_STATUSES and attempt < max_retries:
                            delay = backoff_base * (2 ** (attempt - 1)) + secrets.randbelow(1000) / 1000.0 * 0.2
                            logging.warning(
                                f"Chunk {index} got {response.status}. Retrying in {delay:.2f}s… Body: {text[:300]}")
                            await asyncio.sleep(delay)
                            continue

                        # Non-retryable (or exhausted retries)
                        raise RequestException(
                            f"Chunk {index} failed: {response.status} - {text[:500]}"
                        )

            except Exception as e:
                # Network/timeout — retry if we have attempts left
                if isinstance(e, RequestException) and attempt >= max_retries:
                    logging.error(str(e))
                    raise
                if not isinstance(e, RequestException) and attempt < max_retries:

                    delay = backoff_base * (2 ** (attempt - 1)) + secrets.randbelow(1000) / 1000.0 * 0.2
                    logging.warning(f"Chunk {index} error: {e}. Retrying in {delay:.2f}s…")
                    await asyncio.sleep(delay)
                    continue
                    return None
                # Exhausted retries
                logging.error(f"Chunk {index} failed after {attempt} attempts: {e}")
                raise

    async def post_min_max_values_bulk(self, payload, session, semaphore, chunk_size=100000,
                                       max_retries: int = 3, backoff_base: float = 0.5):
        """
        Concurrent bulk upload with bounded concurrency via `semaphore`.
        Expects `payload` from prepare_min_max_payload (plain dict values).
        """
        values = payload.get("values", [])
        if not values:
            logging.info("No min/max values to post. Skipping bulk upload.")
            return

        url = f'{self.base_url}/api/minMaxDataElements/upsert'
        data_set = payload["dataSet"]
        total = len(values)

        # Slice into chunks
        chunks = []
        for i in range(0, total, chunk_size):
            chunk = values[i:i + chunk_size]
            chunks.append((i // chunk_size + 1, {"dataSet": data_set, "values": chunk}))

        start_time = asyncio.get_event_loop().time()

        # Fire tasks (bounded by semaphore inside _post_chunk)
        tasks = [
            self._post_chunk(url, chunk_payload, session, semaphore, index,
                             max_retries=max_retries, backoff_base=backoff_base)
            for index, chunk_payload in chunks
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate totals and handle failures
        total_successful = 0
        total_ignored = 0
        first_error = None

        for idx, result in enumerate(results, start=1):
            if isinstance(result, Exception):
                # capture first error to raise after aggregation
                if first_error is None:
                    first_error = result
                logging.error(f"Chunk {idx} failed: {result}")
            else:
                successful, ignored = result
                total_successful += successful
                total_ignored += ignored

        # Update tracker once (avoids interleaved updates from concurrent tasks)
        self.result_tracker.add_imported(total_successful)
        self.result_tracker.add_ignored(total_ignored)

        elapsed = asyncio.get_event_loop().time() - start_time
        logging.info(f"Posted {len(chunks)} chunks ({total} values) in {elapsed:.2f}s; "
                     f"successful={total_successful}, ignored={total_ignored}.")

        # If any chunk failed, surface the error (you can choose to swallow it if partial success is OK)
        if first_error:
            raise first_error

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
        fields = ['id','name','organisationUnits', 'periodType', 'dataSetElements[dataElement[id,valueType],categoryCombo[categoryOptionCombos[id]]']

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
        orgunit_group_members = self._resolve_orgunit_group_members(stage)

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
                'use_dataset_orgunits': stage.get('use_dataset_orgunits', False),
                'org_unit_groups': stage.get('org_unit_groups', []),
                'orgunit_group_members': orgunit_group_members,
                'filtered_data_elements': filtered_data_elements,
                'completeness_threshold': stage.get('completeness_threshold',
                                                    self.config.get("completeness_threshold", 0.1)),
                'groups': stage.get('groups'),
            })
            #Add the missing_data_min and missing_data_max to the prepared stage if they exist
            if 'missing_data_min' in stage:
                prepared_stages[-1]['missing_data_min'] = stage['missing_data_min']
            if 'missing_data_max' in stage:
                prepared_stages[-1]['missing_data_max'] = stage['missing_data_max']

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

        if prepared_stage.get('orgunit_group_members'):
            org_units = prepared_stage.get('orgunit_group_members', [])
        else:
            org_units = prepared_stage.get('org_units', [])

        tasks = [
            self.fetch_datavalues_for_orgunit(prepared_stage, ou, session, semaphore)
            for ou in org_units
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
            logging.warning(f"No values found for DE {de_id} in OU {ou_id}. Skipping min/max calculation.")
            self.result_tracker.add_missing()
            return MinMaxRecord(
                dataElement=de_id,
                organisationUnit=ou_id,
                optionCombo=coc_id,
                min=None,
                max=None,
                generated=True,
                comment="No values found"
            )

        min_value_offset, periods_with_data, values = self._adjust_values(de_id, ou_id, values)
        completeness_threshold = float(stage.get("completeness_threshold", self.config.get("completeness_threshold", 0.1)))
        period_count = stage.get("period_count")
        required_periods = math.ceil(period_count * completeness_threshold)

        if periods_with_data < required_periods:
            self.result_tracker.add_missing()
            logging.debug(f"Not enough data for DE {de_id} in OU {ou_id}. Required: {required_periods}, found: {periods_with_data}.")
            if stage.get("missing_data_min") is not None and stage.get("missing_data_max") is not None:
                logging.debug(f"Using configured missing data min/max for DE {de_id} in OU {ou_id}.")
                return MinMaxRecord(
                    dataElement=de_id,
                    organisationUnit=ou_id,
                    optionCombo=coc_id,
                    min=stage.get("missing_data_min"),
                    max=stage.get("missing_data_max"),
                    generated=True,
                    comment="Configured missing data min/max"
                )
            else:
                return MinMaxRecord(
                    dataElement=de_id,
                    organisationUnit=ou_id,
                    optionCombo=coc_id,
                    min=None,
                    max=None,
                    generated=True,
                    comment="Not enough data and no missing data min/max configured"
                )

        self.result_tracker.add_valid()
        median_val = statistics.median(values)

        try:
            method, threshold = select_method_for_median(stage.get("groups", []), median_val)
        except ValueError as e:
            self.result_tracker.add_error()
            logging.error(f"Error selecting method for DE {de_id}/COC {coc_id} in OU {ou_id}: {e}")
            return MinMaxRecord(
                dataElement=de_id,
                organisationUnit=ou_id,
                optionCombo=coc_id,
                min=None,
                max=None,
                generated=True,
                comment="No method group found. Consider to increase limitMedian value."
            )

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
                return MinMaxRecord(
                    dataElement=de_id,
                    organisationUnit=ou_id,
                    optionCombo=coc_id,
                    min=None,
                    max=None,
                    generated=True,
                    comment="Invalid constant values"
                )
            if min_constant >= max_constant:
                self.result_tracker.add_error()
                logging.error(f"Min constant is greater than or equal to max constant for DE {de_id} in OU {ou_id}: {min_constant} > {max_constant}")
                return MinMaxRecord(
                    dataElement=de_id,
                    organisationUnit=ou_id,
                    optionCombo=coc_id,
                    min=None,
                    max=None,
                    generated=True,
                    comment="Min constant is greater than or equal to max constant"
                )
            val_min = min_constant
            val_max = max_constant
            comment = "CONSTANT"
        else:
            val_min, val_max, comment = compute_statistical_bounds(values, method, threshold)

            if not math.isfinite(val_min) or not math.isfinite(val_max):
                self.result_tracker.add_fallback()
                val_min, val_max = past_values_max_bounds(values, 1.5)
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
            logging.warning(f"Min and max are equal for DE {de_id}/COC {coc_id} in OU {ou_id} with values: {values}")
            return MinMaxRecord(
                dataElement=de_id,
                organisationUnit=ou_id,
                optionCombo=coc_id,
                min=None,
                max=None,
                generated=True,
                comment="Min and max are equal"
            )

        return MinMaxRecord(
            dataElement=de_id,
            organisationUnit=ou_id,
            optionCombo=coc_id,
            min=val_min,
            max=val_max,
            generated=False,
            comment=comment
        )

    @staticmethod
    def _adjust_values(de_id, ou_id, values):
        # Filter out non-numeric values
        values = [v for v in values if isinstance(v, (int, float))]
        # Adjust numbers to be positive, as min/max values are always positive
        min_value = min(values)
        # Arbitrary small epsilon to avoid zero values which will lead to problems with Box/Cox
        epsilon = 1e-3
        if min_value < 0:
            min_value_offset = abs(min_value) + epsilon
            values = [v + min_value_offset for v in values]
            logging.info(f"Adjusted values for DE {de_id} in OU {ou_id} to be positive: {values}")
        else:
            min_value_offset = 0
        periods_with_data = len(values)
        return min_value_offset, periods_with_data, values

    @staticmethod
    def build_minmax_csv_dataframe(raw_values: List[dict], minmax_list: List[dict]) -> pd.DataFrame:
        # --- Raw values -> wide by period ---
        dv = pd.DataFrame(raw_values)
        if dv.empty:
            # Create an empty frame with the expected id columns if no data
            dv = pd.DataFrame(columns=["orgUnit", "dataElement", "categoryOptionCombo", "period", "value"])

        # normalize types
        dv["value"] = pd.to_numeric(dv.get("value"), errors="coerce")
        dv["period"] = dv["period"].astype(str)

        # Make a stable key and pivot
        dv = dv.rename(columns={"orgUnit": "organisationUnit", "categoryOptionCombo": "optionCombo"})
        dv["__key__"] = dv[["organisationUnit", "dataElement", "optionCombo"]].agg("|".join, axis=1)

        periods = sorted(dv["period"].unique().tolist())
        wide = (
            dv.pivot_table(
                index="__key__", columns="period", values="value", aggfunc="first", dropna=False
            )
            .reset_index()
        )

        # split key back to columns
        wide[["organisationUnit", "dataElement", "optionCombo"]] = wide["__key__"].str.split("|", expand=True)
        wide = wide.drop(columns="__key__")

        # --- Min/Max results -> tidy ---
        mm = pd.DataFrame(minmax_list)
        if mm.empty:
            mm = pd.DataFrame(columns=["organisationUnit", "dataElement", "optionCombo", "min", "max", "comment"])

        # ensure expected columns exist
        if "categoryOptionCombo" in mm.columns and "optionCombo" not in mm.columns:
            mm = mm.rename(columns={"categoryOptionCombo": "optionCombo"})
        # keep only needed
        keep = ["organisationUnit", "dataElement", "optionCombo", "min", "max", "comment"]
        for c in keep:
            if c not in mm.columns:
                mm[c] = pd.Series(dtype="object")
        mm = mm[keep].drop_duplicates()

        # --- Join and order columns ---
        out = wide.merge(mm, on=["organisationUnit", "dataElement", "optionCombo"], how="left", validate="many_to_many")
        #Drop the active column if it exists
        if 'active' in out.columns:
            out = out.drop(columns=['active'])

        ordered_cols = ["organisationUnit", "dataElement", "optionCombo"] + periods + ["min", "max", "comment"]
        # Add any periods that weren't in the pivot (if none present)
        for col in ordered_cols:
            if col not in out.columns:
                out[col] = pd.NA
        out = out[ordered_cols]

        return out


    async def analyze_stage(self, stage, session, semaphore):
        """
        Prepare the analysis workbook for the given stage.
        This includes fetching data values and calculating min/max values.
        """
        df = pd.DataFrame()
        prepared_stages = self.prepare_stage(stage)
        for prepared_stage in prepared_stages:
            data_values = await self.fetch_data_for_dataset(prepared_stage, semaphore, session)
            if data_values:
                logging.info(f"Fetched {len(data_values)} data values for analysis.")
                grouped_values = self.group_data_for_dataset(data_values)
                min_max_results = self.calculate_dataset_minmax_values(grouped_values, prepared_stage)
                return self.build_minmax_csv_dataframe(data_values, min_max_results)
            else:
                logging.info("No data values fetched for analysis.")
                df = pd.DataFrame()


    def impute_missing_minmmax_values(self, prepared_stage, min_max_results):
        """
        Impute missing min/max values based on existing data.
        This is a placeholder for any imputation logic you might want to implement.
        """
        #First loop over all orgunits and data elements in the prepared stage. If there is
        # no min/max value in the min_max_results for a given combination of data element, optionCombo and orgunit,
        # create a MinMaxRecord with the   missing_data_max
        #missing_data_min from the stage.
        #Exit early if there are no missing_data_min AND missing_data_max
        if not (prepared_stage.get('missing_data_min') or prepared_stage.get('missing_data_max')):
            logging.info("No missing data min/max values to impute. Skipping imputation.")
            return min_max_results
        imputed_results = []
        existing_keys = {(r.organisationUnit, r.dataElement, r.optionCombo) for r in min_max_results}
        for ou in prepared_stage['dataset_metadata'].get('organisationUnits', []):
            ou_id = ou.get('id')
            for dse in prepared_stage['dataset_metadata'].get('dataSetElements', []):
                de_id = dse['dataElement']['id']
                #If the filtered_data_elements is set, skip the data element if it is not in the list
                if prepared_stage['filtered_data_elements'] and de_id not in prepared_stage['filtered_data_elements']:
                    continue
                #Skip if the data element is not numeric
                if dse['dataElement'].get('valueType') not in NumericValueType.list():
                    logging.debug(f"Skipping non-numeric data element {de_id} in dataset {prepared_stage['dataset_id']}.")
                    continue
                #Loop over the category option combos
                for coc in dse.get('categoryCombo', {}).get('categoryOptionCombos', []):
                    coc_id = coc.get('id')
                    # Create a key for the combination of orgUnit, dataElement and categoryOptionCombo
                    key = (ou_id, de_id, coc_id)

                    if key not in existing_keys:
                        # Create a MinMaxRecord with the missing_data_min and missing_data_max
                        min_value = prepared_stage.get('missing_data_min')
                        max_value = prepared_stage.get('missing_data_max')
                        if min_value is None or max_value is None:
                            logging.warning(f"Missing min/max values for {key}. Skipping imputation.")
                            continue
                        self.result_tracker.add_imputed()
                        imputed_results.append(MinMaxRecord(
                            dataElement=de_id,
                            organisationUnit=ou_id,
                            optionCombo=coc_id,
                            min=min_value,
                            max=max_value,
                            generated=True,
                            comment="Imputed from missing_data_min/max"
                        ))
        # Append the original min_max_results to the imputed results
        imputed_results.extend(min_max_results)
        logging.info(f"Imputed {len(imputed_results) - len(min_max_results)} missing min/max values.")
        return imputed_results

    def _check_can_upload_minmax(self):
        """
        Check if the server supports min/max uploads.
        """
        try:
            permitted_auths = ['F_MIN_MAX_ADD', 'ALL']
            me = self.api_utils.fetch_me()
            if not any(auth in me.get('authorities', []) for auth in permitted_auths):
                logging.error("User does not have permission to add min/max values.")
                return False
            return True
        except Exception as e:
            logging.error(f"Error checking user permissions: {e}")
            return False

    def _resolve_orgunit_group_members(self, stage):
        if not stage.get('org_unit_groups'):
            return []
        else:
            #These maybe comma separated strings
            group_ids = []
            for og in stage.get('org_unit_groups'):
                group_ids.extend([g.strip() for g in og.split(',') if g.strip()])
            if not group_ids:
                return []
            else:
                #Loop over each group and get the ids of each orgunit
                members = set()

                for group_id in group_ids:
                    group_metadata = self.api_utils.fetch_organisation_unit_groups(
                        fields=["id","name","organisationUnits[id]"] ,
                        filters=[f'id:eq:{group_id}']
                    )
                    for ou in group_metadata[0].get('organisationUnits', []):
                        members.add(ou['id'])
                return list(members)





