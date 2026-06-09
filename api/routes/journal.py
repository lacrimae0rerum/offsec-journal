from typing import Any
from fastapi import APIRouter, Body, Depends, HTTPException

from api.core import db, queries
from api.core import journal as journal_core
from api.models.journal import JournalCreate
from api.security import AuthContext, require_authelia
from api.security.rate_limit import tenant_writes

router = APIRouter(prefix="/journal", tags=["journal"])


@router.get("")
async def list_entries(
    status: str | None = None,
    ctx: AuthContext = Depends(require_authelia),
) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_journal(conn, ctx.team_id, status=status)


@router.post("")
async def create_entry(
    body: JournalCreate,
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    tenant_writes.check(ctx.user_id)
    # Validate BEFORE any filesystem mutation — a malformed payload must never
    # reach data/<team>/journal.yaml. This raises JournalError (→ 400) without
    # touching the YAML if body.payload is invalid.
    try:
        journal_core.validate_payload(body.kind, body.payload)
    except journal_core.JournalError as e:
        raise HTTPException(400, str(e)) from e

    try:
        return journal_core.create_entry(
            body.kind, body.payload, ctx.team_slug,
            proposer="human",
            created_by_user_id=ctx.user_id,
        )
    except journal_core.JournalError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{entry_id}/apply")
async def apply(
    entry_id: str,
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    tenant_writes.check(ctx.user_id)
    try:
        return journal_core.apply_entry(
            entry_id, ctx.team_slug, applied_by=ctx.username,
        )
    except journal_core.JournalError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/{entry_id}/reject")
async def reject(
    entry_id: str,
    body: dict = Body(...),
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    tenant_writes.check(ctx.user_id)
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "reject requires reason")
    try:
        return journal_core.reject_entry(
            entry_id, ctx.team_slug, reason, applied_by=ctx.username,
        )
    except journal_core.JournalError as e:
        raise HTTPException(400, str(e)) from e
