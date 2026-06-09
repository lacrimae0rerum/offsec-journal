from typing import Any
from fastapi import APIRouter, Depends

from api.core import db, queries
from api.core.coherence import check_all
from api.security import AuthContext, require_authelia

router = APIRouter(prefix="/coherence", tags=["coherence"])


@router.get("")
async def list_all_warnings(
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    with db.transaction() as conn:
        people = queries.list_people(conn, ctx.team_id)
        skills_by_person = {p["id"]: p["skills"] for p in people}
        warnings = check_all(people, skills_by_person)
        return {"warnings": warnings, "count": len(warnings)}
