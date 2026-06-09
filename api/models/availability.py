from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

AvailabilityKind = Literal["pto", "sick", "training", "overhead", "hold"]


class Availability(BaseModel):
    person_id: str
    kind: AvailabilityKind
    start: date
    end: date
    pct: int = Field(default=100, ge=0, le=100)
    reason: str = ""
    archived: bool = False
