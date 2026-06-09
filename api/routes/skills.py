from fastapi import APIRouter, Depends

from api.core import db, queries
from api.security import require_authelia

router = APIRouter(
    prefix="/skills",
    tags=["skills"],
    dependencies=[Depends(require_authelia)],
)


@router.get("")
async def list_skills(archived: bool = False) -> list[dict]:
    """Skills catalog is shared across teams — no team_id scoping."""
    with db.transaction() as conn:
        return queries.list_skills(conn, include_archived=archived)
