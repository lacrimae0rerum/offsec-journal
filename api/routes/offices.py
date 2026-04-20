from fastapi import APIRouter, Depends

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(prefix="/offices", tags=["offices"], dependencies=[Depends(require_api_key)])


@router.get("")
async def list_offices() -> list[dict]:
    with db.transaction() as conn:
        return queries.list_offices(conn)
