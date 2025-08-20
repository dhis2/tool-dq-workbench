from dataclasses import dataclass
from typing import Optional


@dataclass
class MinMaxRecord:
    dataElement: str
    organisationUnit: str
    optionCombo: str
    min: Optional[int] = None
    max: Optional[int] = None
    generated: bool = False
    comment: str = ""