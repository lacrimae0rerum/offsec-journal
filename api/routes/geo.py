from fastapi import APIRouter, Depends

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(prefix="/geo", tags=["geo"], dependencies=[Depends(require_api_key)])


@router.get("")
async def geo() -> list[dict]:
    """Offices with coords + resident people (by id). Fuel for /map."""
    with db.transaction() as conn:
        offices = queries.list_offices(conn)
        for o in offices:
            o["people"] = [
                r["id"] for r in conn.execute(
                    "SELECT id FROM person WHERE office = ? AND archived = 0 ORDER BY id",
                    (o["office_id"],),
                )
            ]
        return offices
