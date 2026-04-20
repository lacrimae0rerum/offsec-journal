from datetime import datetime
from typing import Literal

from pydantic import BaseModel

EntityType = Literal["person", "project", "client"]


class Note(BaseModel):
    """A note is a block in a markdown file, never a DB row.

    notes/persons/<id>.md, notes/projects/<code>.md, notes/clients/<id>.md.
    Separator line: `--- <iso-ts> | <author> | tags: <csv> ---`.
    Append-only (decision #4). FTS5 indexes the body for /api/search.
    """
    entity_type: EntityType
    entity_id: str
    timestamp: datetime
    author: str
    tags: list[str] = []
    body: str
