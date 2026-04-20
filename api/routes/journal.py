from fastapi import APIRouter, Body, Depends, HTTPException

from api.auth import require_api_key
from api.core import db, queries
from api.core import journal as journal_core
from api.models.journal import JournalCreate

router = APIRouter(prefix="/journal", tags=["journal"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_entries(status: str | None = None) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_journal(conn, status=status)


@router.post("")
async def create_entry(body: JournalCreate) -> dict:
    try:
        return journal_core.create_entry(body.kind, body.payload, proposer="human")
    except Exception as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{entry_id}/apply")
async def apply(entry_id: str, applied_by: str = "human") -> dict:
    try:
        return journal_core.apply_entry(entry_id, applied_by=applied_by)
    except journal_core.JournalError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{entry_id}/reject")
async def reject(entry_id: str, body: dict = Body(...)) -> dict:
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "reject requires reason")
    try:
        return journal_core.reject_entry(entry_id, reason, applied_by=body.get("applied_by", "human"))
    except journal_core.JournalError as e:
        raise HTTPException(400, str(e)) from e
