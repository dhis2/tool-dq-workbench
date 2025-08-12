from abc import ABC, abstractmethod

from app.core.period_type import PeriodType

from app.core.period_utils import Dhis2PeriodUtils
from app.core.api_utils import Dhis2ApiUtils
import re
from app.core.time_unit import TimeUnit
from typing import Optional

class StageAnalyzer(ABC):
    def __init__(self, config, base_url, headers):
        self.config = config
        self.base_url = config['server'].get('base_url', base_url)
        self.d2_token = config['server'].get('d2_token', '')
        self.headers = headers
        self.default_coc = config['server'].get('default_coc', 'HllvX50cXC0')
        self.api_utils = Dhis2ApiUtils(self.base_url, self.d2_token)

    @abstractmethod
    async def run_stage(self, stage: dict, session, semaphore):
        """
        Run a stage and return a list of data values to post.
        """
        pass
    
    @staticmethod
    def get_start_date(stage):
        """Convenience wrapper for getting start date from duration"""
        return Dhis2PeriodUtils.get_start_date_from_today(stage['params']['duration'])

    async def get_organisation_units_at_level(self, level, session, semaphore):
        return await self.api_utils.get_organisation_units_at_level(level, session, semaphore)

    @staticmethod
    def validate_duration_string(value: str) -> Optional[str]:
        match = re.match(r"^\s*(\d+)\s+(\w+)\s*$", value.strip(), re.IGNORECASE)
        if not match:
            return "Expected format like '12 months', '5 years', etc."

        amount, unit = match.groups()
        if int(amount) <= 0:
            return "Duration must be greater than 0."
        if unit.lower() not in TimeUnit.list():
            return f"Invalid duration provided '{unit}'. Must be one of: {', '.join(TimeUnit.list())}"

        return None
