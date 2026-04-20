"""Pydantic v2 models mirroring the YAML source-of-truth.

Every entity has `archived: bool = False` (soft delete — decision #2).
The DB row stores the same shape; sync.py treats models as the canonical form.
"""
from api.models.skill import Skill
from api.models.office import Office
from api.models.person import Person, PersonSkill
from api.models.project import Project, RequiredSkill
from api.models.assignment import Assignment
from api.models.availability import Availability
from api.models.client import Client, Contact
from api.models.journal import JournalEntry, JournalPayload
from api.models.note import Note

__all__ = [
    "Skill",
    "Office",
    "Person",
    "PersonSkill",
    "Project",
    "RequiredSkill",
    "Assignment",
    "Availability",
    "Client",
    "Contact",
    "JournalEntry",
    "JournalPayload",
    "Note",
]
