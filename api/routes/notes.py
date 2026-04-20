from fastapi import APIRouter, Depends, HTTPException

from api.auth import require_api_key
from api.core import notes as notes_core
from api.models.note import EntityType
from pydantic import BaseModel

router = APIRouter(prefix="/notes", tags=["notes"], dependencies=[Depends(require_api_key)])


class NoteCreate(BaseModel):
    entity_type: EntityType
    entity_id: str
    body: str
    author: str = "human"
    tags: list[str] = []


@router.get("")
async def read_notes(entity_type: EntityType, entity_id: str) -> list[dict]:
    try:
        return notes_core.read_all(entity_type, entity_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("")
async def append_note(body: NoteCreate) -> dict:
    try:
        note = notes_core.append(
            body.entity_type, body.entity_id, body.body, body.author, body.tags
        )
        # Not calling sync here — on-demand via /api/sync or next journal apply.
        # Users expecting the note in search immediately can POST /api/sync.
        return note
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
