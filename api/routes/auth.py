"""Identity endpoint consumed by the frontend on page load."""
from typing import Any

from fastapi import APIRouter, Depends

from api.config import settings
from api.security import AuthContext, require_authelia

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
async def me(ctx: AuthContext = Depends(require_authelia)) -> dict[str, Any]:
    """Current user envelope. The SPA calls this to paint the team badge,
    display name, and decide whether to show admin-only UI elements.
    `logout_url` is optional (empty by default): the journal does not own the
    session, so the frontend hides the logout affordance when it's empty."""
    return {
        "username": ctx.username,
        "display_name": ctx.display_name,
        "email": ctx.email,
        "team": {"slug": ctx.team_slug, "name": ctx.team_name},
        "role": ctx.role,
        "logout_url": settings.authelia_logout_url,
    }
