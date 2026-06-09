from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from api.core import db, queries
from api.security import AuthContext, require_authelia

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
async def list_clients(
    archived: bool = False,
    ctx: AuthContext = Depends(require_authelia),
) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_clients(conn, ctx.team_id, include_archived=archived)


@router.get("/{client_id}")
async def get_client(
    client_id: str,
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    with db.transaction() as conn:
        c = queries.get_client(conn, ctx.team_id, client_id)
        if c is None:
            raise HTTPException(404, f"client {client_id} not found")
        return c
