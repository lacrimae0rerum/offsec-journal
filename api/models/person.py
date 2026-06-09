from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

GlobalLevel = Literal["junior", "intermediate", "senior", "master"]


class PersonSkill(BaseModel):
    skill_id: str
    level: int = Field(ge=0, le=5)
    last_used_on_project: str | None = None
    growth_interest: bool = False


class Person(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    full_name: str
    office: str  # office_id
    city: str
    timezone: str = "CET"
    languages: list[str] = []
    base_role: str = "pentester"
    global_level: GlobalLevel = "junior"
    contractual_fte: float = Field(default=1.0, ge=0.0, le=1.0)
    start_date: date
    archived: bool = False
    skills: list[PersonSkill] = []
