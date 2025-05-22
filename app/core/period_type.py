from enum import Enum


class PeriodType(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

    @classmethod
    def values(cls):
        return [member.value for member in cls]