# app/core/time_unit.py

from enum import Enum

class TimeUnit(str, Enum):
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    QUARTERS = "quarters"
    YEARS = "years"

    @classmethod
    def list(cls):
        return [pt.value for pt in cls]
