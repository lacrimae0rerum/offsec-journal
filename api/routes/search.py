from fastapi import APIRouter, Depends

from api.auth import require_api_key
from api.core import db, queries

router = APIRouter(tags=["search"], dependencies=[Depends(require_api_key)])


@router.get("/search")
async def search(q: str = "") -> dict:
    with db.transaction() as conn:
        return queries.search(conn, q)
