import asyncio
import logging
from requests import RequestException

import requests.exceptions

from app.core.period_utils import Dhis2PeriodUtils
from app.core.api_utils import Dhis2ApiUtils
from app.core.numeric_value_types import NumericValueType
from app.core.time_unit import TimeUnit
import pandas as pd
import numpy as np
import math
from scipy.stats import median_abs_deviation
from scipy import stats
from scipy.special import inv_boxcox
from tqdm import tqdm
import warnings
import argparse

class MinMaxGenerator:
    def __init__(self, config, base_url, headers):
        self.config = config
        self.base_url = config.get('server').get('base_url', base_url)
        self.headers = headers
        self.default_coc = config['server'].get('default_coc', 'HllvX50cXC0')
        self.api_utils = Dhis2ApiUtils(self.base_url)
        self.period_utils = Dhis2PeriodUtils()
        self.dataset_metadata = self.get_dataset_metadata(config.get('dataset'))

    async def run_stage(self, stage: dict, session, semaphore):
        """
        Run a stage, including fetching data values,
        generating min/max values,
        and posting the results to the appropriate endpoint based on the server version.
        """
        raise NotImplementedError("run_stage() must be implemented")

    async def post_min_max_values_bulk(self, values, session, semaphore):
        """
        Post the min/max values to the server in bulk.
        (Only available in DHIS2 2.41+)
        """
        url = f'{self.base_url}/api/minMaxDataElements/upsert'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self.headers['Authorization']
        }
        # Placeholder: implement actual POST logic here
        return None

    async def post_min_max_values(self, values, session, semaphore):
        """
        Post min/max values using the legacy endpoint (2.40 and below).
        """
        url = f'{self.base_url}/api/dataEntry/minMaxValues'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self.headers['Authorization']
        }
        # Placeholder: implement actual POST logic here
        return None


    async def get_datavalues_for_orgunit(self, dataset, org_unit, start_date, end_date, session, semaphore):
        """
        Fetch data values for a specific organisation unit within the given date range.
        """
        url = f'{self.base_url}/api/dataValueSets'
        params = {
            'dataSet': dataset,
            'orgUnit': org_unit,
            'startDate': start_date,
            'endDate': end_date,
            'children': 'true'
        }
        async with semaphore:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    resp = await response.json()
                    des_in_dataset = self.dataset_metadata.get('dataSetElements')
                    #Filter these to get the numeric data elements
                    numeric_des = [de for de in des_in_dataset if de.get('dataElement', {}).get('valueType') in NumericValueType.list()]

                else:
                    raise RequestException(f"Failed to fetch data values: {response.status} - {await response.text()}")


    def get_dataset_metadata(self, dataset):
        """
        Fetch metadata for a specific dataset.
        """
        resp = self.api_utils.fetch_metadata_list(
            endpoint='dataSets',
            key='id',
            filters=f'filter=id:eq:{dataset}',
            fields='id,periodType,dataSetElements[dataElement[id,valueType]]',
        )
        if resp:
            resp =  resp[0]
        else:
            raise ValueError(f"Dataset {dataset} not found in metadata.")

    ## Get the number of periods we are looking at in total (i.e. denominator for looking at completeness)
    async def get_data_values(self, stage, session, semaphore):


        dataset = self.dataset_metadata.get('id')
        dataset_period_type = self.dataset_metadata.get('periodType')
        #Get the previous period of this period type
        current_period = self.period_utils.get_current_period(dataset_period_type)
        periods = self.period_utils.get_previous_periods(current_period, dataset_period_type, stage.get('previous_periods', 12))
        #Get the start date of the data, which will be the start date of the first period
        start_date = self.period_utils.get_start_date_from_period(periods[0])
        end_date = self.period_utils.get_end_date_from_period(periods[-1])
        #There can be multiple orgunits in the stage, so use the semaphore and loop over these
        org_units = stage.get('org_units')

        tasks = [
            self.get_datavalues_for_orgunit(dataset, org_unit, start_date, end_date, session, semaphore)
            for org_unit in org_units
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        data_values = []
        for result in results:
            if isinstance(result, Exception):
                logging.error(f"Error fetching data values: {result}")
            elif isinstance(result, dict):
                data_values.extend(result.get('dataValues', []))

