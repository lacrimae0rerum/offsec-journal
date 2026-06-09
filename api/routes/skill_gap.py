from fastapi import APIRouter, Depends

from api.core import db, queries
from api.security import AuthContext, require_authelia

router = APIRouter(tags=["skill-gap"])


@router.get("/skill-gap")
async def skill_gap(
    scope: str = "pipeline",
    ctx: AuthContext = Depends(require_authelia),
) -> list[dict]:
    if scope not in ("pipeline", "active", "closed"):
        scope = "pipeline"
    with db.transaction() as conn:
        return queries.skill_gap(conn, ctx.team_id, scope=scope)
