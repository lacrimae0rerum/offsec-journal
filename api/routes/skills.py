from fastapi import APIRouter, Depends

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(prefix="/skills", tags=["skills"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_skills(archived: bool = False) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_skills(conn, include_archived=archived)
