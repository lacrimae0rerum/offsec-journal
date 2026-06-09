from typing import Any
from fastapi import APIRouter, Depends

from api.core import db, queries
from api.security import AuthContext, require_authelia

router = APIRouter(tags=["search"])


def _csv(value: str | None) -> list[str] | None:
    """Parse a comma-separated query param into a clean list, or None if empty."""
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


@router.get("/search")
async def search(
    q: str = "",
    types: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    tags: str | None = None,
    ctx: AuthContext = Depends(require_authelia),
) -> dict[str, Any]:
    with db.transaction() as conn:
        return queries.search(
            conn,
            ctx.team_id,
            q,
            types=_csv(types),
            date_from=date_from or None,
            date_to=date_to or None,
            tags=_csv(tags),
        )
