from fastapi import APIRouter, Depends

from api.core import db, queries
from api.security import AuthContext, require_authelia

router = APIRouter(prefix="/offices", tags=["offices"])


@router.get("")
async def list_offices(ctx: AuthContext = Depends(require_authelia)) -> list[dict]:
    with db.transaction() as conn:
        return queries.list_offices(conn, ctx.team_id)
