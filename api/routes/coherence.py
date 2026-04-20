from fastapi import APIRouter, Depends

from api.auth import require_api_key
from api.core import db, queries
from api.core.coherence import check_all

router = APIRouter(prefix="/coherence", tags=["coherence"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_all_warnings() -> dict:
    with db.transaction() as conn:
        people = queries.list_people(conn)
        skills_by_person = {p["id"]: p["skills"] for p in people}
        warnings = check_all(people, skills_by_person)
        return {"warnings": warnings, "count": len(warnings)}
