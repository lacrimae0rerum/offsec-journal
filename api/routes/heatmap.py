from typing import Any
from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from api.core import db, queries
from api.security import AuthContext, require_authelia

router = APIRouter(tags=["heatmap"])


@router.get("/heatmap")
async def heatmap(
    start: str,
    end: str,
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
    except ValueError as exc:
        raise HTTPException(400, f"invalid date: {exc}") from exc
    if s > e:
        raise HTTPException(400, "start > end")
    with db.transaction() as conn:
        return queries.heatmap(conn, ctx.team_id, s, e)
