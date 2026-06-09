from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

AssignmentRole = Literal["lead", "executor", "reviewer", "shadow"]


class Assignment(BaseModel):
    person_id: str
    project_code: str
    dedication_pct: int = Field(ge=0, le=200)  # >100 is over-allocation, allowed but flagged
    start: date
    end: date
    role: AssignmentRole = "executor"
    archived: bool = False
