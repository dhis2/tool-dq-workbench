# app/core/value_type.py

from enum import Enum

class NumericValueType(str, Enum):
    INTEGER = "INTEGER"
    INTEGER_POSITIVE = "INTEGER_POSITIVE"
    NUMBER = "NUMBER"
    PERCENTAGE = "PERCENTAGE"
    INTEGER_ZERO_OR_POSITIVE = "INTEGER_ZERO_OR_POSITIVE"

    @classmethod
    def list(cls):
        return [v.value for v in cls]
