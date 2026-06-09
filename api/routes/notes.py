from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.core import notes as notes_core
from api.models.note import EntityType
from api.security import AuthContext, require_authelia
from api.security.rate_limit import tenant_writes

router = APIRouter(prefix="/notes", tags=["notes"])


class NoteCreate(BaseModel):
    entity_type: EntityType
    entity_id: str
    body: str
    author: str = "human"
    tags: list[str] = []


@router.get("")
async def read_notes(
    entity_type: EntityType,
    entity_id: str,
    ctx: AuthContext = Depends(require_authelia),
) -> list[dict[str, Any]]:
    try:
        return notes_core.read_all(entity_type, entity_id, ctx.team_slug)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("")
async def append_note(
    body: NoteCreate,
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    tenant_writes.check(ctx.user_id)
    try:
        # Author defaults to the authenticated username if body didn't specify one.
        author = body.author if body.author and body.author != "human" else ctx.username
        return notes_core.append(
            body.entity_type, body.entity_id, body.body, author,
            ctx.team_slug, tags=body.tags,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
