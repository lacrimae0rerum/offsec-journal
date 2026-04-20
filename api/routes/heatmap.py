from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(tags=["heatmap"], dependencies=[Depends(require_api_key)])


@router.get("/heatmap")
async def heatmap(start: str, end: str) -> dict:
    try:
        s = date.fromisoformat(start)
        e = date.fromisoformat(end)
    except ValueError as exc:
        raise HTTPException(400, f"invalid date: {exc}") from exc
    if s > e:
        raise HTTPException(400, "start > end")
    with db.transaction() as conn:
        return queries.heatmap(conn, s, e)
