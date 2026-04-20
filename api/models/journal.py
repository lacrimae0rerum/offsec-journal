"""Journal entries — typed, append-only write-path for structural mutations.

Every kind maps to a specific payload shape. The backend validates the payload
on POST /api/journal and rejects malformed entries before they ever land in
data/journal.yaml. apply() dispatches on kind to the right core.queries fn.
"""
from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

JournalProposer = Literal["llm", "human"]
JournalStatus = Literal["pending", "applied", "rejected"]

JournalKind = Literal[
    "assign",
    "unassign",
    "availability",
    "skill_update",
    "person_create",
    "person_update",
    "person_archive",
    "project_create",
    "project_update",
    "project_archive",
    "client_create",
    "client_update",
    "client_archive",
    "contact_add",
    "contact_update",
    "contact_remove",
    "office_create",
    "office_update",
    "office_archive",
    "skill_catalog_create",
    "skill_catalog_archive",
    "skill_label_update",
]


# ---------- Payloads (one model per kind) ----------
class AssignPayload(BaseModel):
    kind: Literal["assign"] = "assign"
    person_id: str
    project_code: str
    dedication_pct: int = Field(ge=0, le=200)
    start: date
    end: date
    role: Literal["lead", "executor", "reviewer", "shadow"] = "executor"


class UnassignPayload(BaseModel):
    kind: Literal["unassign"] = "unassign"
    person_id: str
    project_code: str


class AvailabilityPayload(BaseModel):
    kind: Literal["availability"] = "availability"
    person_id: str
    availability_kind: Literal["pto", "sick", "training", "overhead", "hold"]
    start: date
    end: date
    pct: int = Field(default=100, ge=0, le=100)
    reason: str = ""


class SkillUpdatePayload(BaseModel):
    kind: Literal["skill_update"] = "skill_update"
    person_id: str
    skill_id: str
    level: int = Field(ge=0, le=5)
    growth_interest: bool | None = None
    rationale: str = ""


class PersonCreatePayload(BaseModel):
    kind: Literal["person_create"] = "person_create"
    id: str
    full_name: str
    office: str
    city: str = ""
    timezone: str = "CET"
    languages: list[str] = []
    base_role: str = "pentester"
    global_level: Literal["junior", "intermediate", "senior", "master"] = "junior"
    contractual_fte: float = 1.0
    start_date: date


class PersonUpdatePayload(BaseModel):
    kind: Literal["person_update"] = "person_update"
    id: str
    full_name: str | None = None
    office: str | None = None
    city: str | None = None
    timezone: str | None = None
    languages: list[str] | None = None
    base_role: str | None = None
    global_level: Literal["junior", "intermediate", "senior", "master"] | None = None
    contractual_fte: float | None = None


class PersonArchivePayload(BaseModel):
    kind: Literal["person_archive"] = "person_archive"
    id: str
    archived: bool = True


class ProjectCreatePayload(BaseModel):
    kind: Literal["project_create"] = "project_create"
    code: str
    client_alias: str
    type: str
    window_start: date
    window_end: date
    estimated_hours: int = 0
    status: Literal["pipeline", "active", "closed"] = "pipeline"
    required_skills: list[dict] = []


class ProjectUpdatePayload(BaseModel):
    kind: Literal["project_update"] = "project_update"
    code: str
    client_alias: str | None = None
    type: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    estimated_hours: int | None = None
    status: Literal["pipeline", "active", "closed"] | None = None
    required_skills: list[dict] | None = None


class ProjectArchivePayload(BaseModel):
    kind: Literal["project_archive"] = "project_archive"
    code: str
    archived: bool = True


class ClientCreatePayload(BaseModel):
    kind: Literal["client_create"] = "client_create"
    id: str
    name: str
    sector: str = ""
    size: str = ""
    country: str = ""
    description: str = ""


class ClientUpdatePayload(BaseModel):
    kind: Literal["client_update"] = "client_update"
    id: str
    name: str | None = None
    sector: str | None = None
    size: str | None = None
    country: str | None = None
    description: str | None = None


class ClientArchivePayload(BaseModel):
    kind: Literal["client_archive"] = "client_archive"
    id: str
    archived: bool = True


class ContactAddPayload(BaseModel):
    kind: Literal["contact_add"] = "contact_add"
    client_id: str
    name: str
    role: str = ""
    email: str = ""
    phone: str = ""


class ContactUpdatePayload(BaseModel):
    kind: Literal["contact_update"] = "contact_update"
    client_id: str
    contact_index: int
    name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None


class ContactRemovePayload(BaseModel):
    kind: Literal["contact_remove"] = "contact_remove"
    client_id: str
    contact_index: int


class OfficeCreatePayload(BaseModel):
    kind: Literal["office_create"] = "office_create"
    office_id: str
    city: str
    country: str = ""
    lat: float = 0.0
    lon: float = 0.0


class OfficeUpdatePayload(BaseModel):
    kind: Literal["office_update"] = "office_update"
    office_id: str
    city: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None


class OfficeArchivePayload(BaseModel):
    kind: Literal["office_archive"] = "office_archive"
    office_id: str
    archived: bool = True


class SkillCatalogCreatePayload(BaseModel):
    kind: Literal["skill_catalog_create"] = "skill_catalog_create"
    id: str  # snake_case, used as skill_id throughout
    label_es: str
    description: str = "TODO: operator-defined"


class SkillCatalogArchivePayload(BaseModel):
    kind: Literal["skill_catalog_archive"] = "skill_catalog_archive"
    id: str
    archived: bool = True


class SkillLabelUpdatePayload(BaseModel):
    kind: Literal["skill_label_update"] = "skill_label_update"
    skill_id: str
    label_es: str | None = None
    description: str | None = None


JournalPayload = Annotated[
    Union[
        AssignPayload, UnassignPayload, AvailabilityPayload, SkillUpdatePayload,
        PersonCreatePayload, PersonUpdatePayload, PersonArchivePayload,
        ProjectCreatePayload, ProjectUpdatePayload, ProjectArchivePayload,
        ClientCreatePayload, ClientUpdatePayload, ClientArchivePayload,
        ContactAddPayload, ContactUpdatePayload, ContactRemovePayload,
        OfficeCreatePayload, OfficeUpdatePayload, OfficeArchivePayload,
        SkillCatalogCreatePayload, SkillCatalogArchivePayload, SkillLabelUpdatePayload,
    ],
    Field(discriminator="kind"),
]


class JournalEntry(BaseModel):
    id: str = Field(pattern=r"^[0-9A-HJKMNP-TV-Z]{26}$")  # ULID crockford alphabet
    timestamp: datetime
    proposer: JournalProposer
    kind: JournalKind
    payload: dict  # stored raw; validated at POST time via JournalPayload
    status: JournalStatus = "pending"
    applied_at: datetime | None = None
    applied_by: str | None = None
    rejected_reason: str | None = None


class JournalCreate(BaseModel):
    """Payload for POST /api/journal. Proposer=human is filled by server."""
    kind: JournalKind
    payload: dict
