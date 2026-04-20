from fastapi import APIRouter, Depends

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(tags=["skill-gap"], dependencies=[Depends(require_api_key)])


@router.get("/skill-gap")
async def skill_gap(scope: str = "pipeline") -> list[dict]:
    if scope not in ("pipeline", "active", "closed"):
        scope = "pipeline"
    with db.transaction() as conn:
        return queries.skill_gap(conn, scope=scope)
