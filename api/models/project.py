from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ProjectType = Literal[
    "pentest_web",
    "pentest_infra",
    "red_team",
    "purple",
    "cti_retainer",
    "research",
    "internal",
]
ProjectStatus = Literal["pipeline", "active", "closed"]


class RequiredSkill(BaseModel):
    skill_id: str
    weight: int = Field(ge=1, le=3)
    min_level: int = Field(ge=1, le=5)


class Project(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2,4}-\d{4}-\d{3}$")
    client_alias: str  # references Client.id; "interno" for internal work
    type: ProjectType
    window_start: date
    window_end: date
    estimated_hours: int = Field(ge=0)
    status: ProjectStatus = "pipeline"
    archived: bool = False
    required_skills: list[RequiredSkill] = []
