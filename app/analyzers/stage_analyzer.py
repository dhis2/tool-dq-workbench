from abc import ABC, abstractmethod
from app.core.period_utils import Dhis2PeriodUtils
from app.core.api_utils import Dhis2ApiUtils

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

    def get_start_date(self, stage):
        """Convenience wrapper for getting start date from duration"""
        return Dhis2PeriodUtils.get_start_date_from_today(stage['duration'])

    async def get_organisation_units_at_level(self, level, session):
        return await self.api_utils.get_organisation_units_at_level(level, session)
