from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from api.core import db, queries
from api.security import AuthContext, require_authelia

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(
    status: str | None = None,
    archived: bool = False,
    ctx: AuthContext = Depends(require_authelia),
) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_projects(
            conn, ctx.team_id, status=status, include_archived=archived
        )


@router.get("/{code}")
async def get_project(
    code: str,
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    with db.transaction() as conn:
        p = queries.get_project(conn, ctx.team_id, code)
        if p is None:
            raise HTTPException(404, f"project {code} not found")
        return p
