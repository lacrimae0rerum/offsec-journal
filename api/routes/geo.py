from fastapi import APIRouter, Depends

from api.core import db, queries
from api.security import AuthContext, require_authelia

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("")
async def geo(ctx: AuthContext = Depends(require_authelia)) -> list[dict]:
    """Offices with coords + resident people (by id), team-scoped. Fuel for /map."""
    with db.transaction() as conn:
        offices = queries.list_offices(conn, ctx.team_id)
        for o in offices:
            o["people"] = [
                r["id"] for r in conn.execute(
                    """SELECT id FROM person
                       WHERE office = ? AND team_id = ? AND archived = 0
                       ORDER BY id""",
                    (o["office_id"], ctx.team_id),
                )
            ]
        return offices
