from abc import ABC, abstractmethod
from app.core.period_utils import Dhis2PeriodUtils
from app.core.api_utils import Dhis2ApiUtils
import re
from app.core.time_unit import TimeUnit
from typing import Optional

class StageAnalyzer(ABC):
    def __init__(self, config, base_url, headers):
        self.config = config
        self.base_url = base_url
        self.headers = headers
        self.default_coc = config['server'].get('default_coc', 'HllvX50cXC0')

        self.api_utils = Dhis2ApiUtils(self.base_url)

    @abstractmethod
    async def run_stage(self, stage: dict, session, semaphore):
        """
        Run a stage and return a list of data values to post.
        """
        pass
    
    @staticmethod
    def get_start_date(stage):
        """Convenience wrapper for getting start date from duration"""
        return Dhis2PeriodUtils.get_start_date_from_today(stage['duration'])

    async def get_organisation_units_at_level(self, level, session):
        return await self.api_utils.get_organisation_units_at_level(level, session)

    @staticmethod
    def validate_duration_string(value: str) -> Optional[str]:
        match = re.match(r"^\s*(\d+)\s+(\w+)\s*$", value.strip(), re.IGNORECASE)
        if not match:
            return "Expected format like '12 monthly', '1 yearly', etc."

        amount, unit = match.groups()
        if int(amount) <= 0:
            return "Duration must be greater than 0."
        if unit.lower() not in PeriodType.list():
            return f"Invalid period type '{unit}'. Must be one of: {', '.join(PeriodType.list())}"

        return None
