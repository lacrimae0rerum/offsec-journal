"""Authelia forward-auth middleware.

Reads Remote-User from request headers (set by nginx after forward-auth OK),
validates against the local `user` table, and returns an AuthContext with
the user's team and role.

Trust model:
  - request.client.host must be in settings.trusted_proxy_ips_list
    (only nginx on loopback should be able to reach the app).
  - No shared secret: with SSH restricted to the box, a secret in a file
    readable by other local users adds no real defense.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from ulid import ULID

from api.config import settings
from api.core import db
from api.security.audit import log_event


@dataclass(frozen=True)
class AuthContext:
    """Identity + authorization envelope passed via request.state to handlers.

    team_id == team_slug in the current schema (id equals slug). Both are
    exposed to keep routers readable and to not couple them to that decision.
    """
    user_id: str
    username: str
    team_id: str
    team_slug: str
    team_name: str
    role: str
    display_name: str = ""
    email: str = ""


def get_user_by_username(conn: sqlite3.Connection, username: str) -> dict | None:
    """Fetch user + team info by username (case-insensitive)."""
    row = conn.execute(
        """SELECT
             u.id            AS user_id,
             u.username      AS username,
             u.team_id       AS team_id,
             u.role          AS role,
             u.display_name  AS display_name,
             u.email         AS email,
             u.archived      AS archived,
             t.slug          AS team_slug,
             t.name          AS team_name
           FROM user u
             JOIN team t ON t.id = u.team_id
           WHERE u.username = ?""",
        (username.lower(),),
    ).fetchone()
    return dict(row) if row else None


def touch_last_seen(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute(
        "UPDATE user SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
        (user_id,),
    )


def _ctx_from_user(user: dict) -> AuthContext:
    return AuthContext(
        user_id=user["user_id"],
        username=user["username"],
        team_id=user["team_id"],
        team_slug=user["team_slug"],
        team_name=user["team_name"],
        role=user["role"],
        display_name=user["display_name"] or "",
        email=user["email"] or "",
    )


_VALID_ROLES = {"member", "admin"}


def _autoprovision_user(conn: sqlite3.Connection, username: str) -> dict:
    """Insert a new row in the default team for an unknown Authelia user.

    Only called when settings.single_tenant_mode is true. The default team must
    already exist in the team table (seeded from teams.yaml). The role assigned
    is settings.single_tenant_default_role (default 'member'). Returns the
    same shape that get_user_by_username returns.
    """
    team_slug = settings.single_tenant_default_team
    team_row = conn.execute(
        "SELECT id, slug, name FROM team WHERE slug = ?",
        (team_slug,),
    ).fetchone()
    if team_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"single-tenant default team '{team_slug}' not in DB",
        )
    role = (settings.single_tenant_default_role or "member").strip().lower()
    if role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"invalid single_tenant_default_role='{role}'",
        )
    user_id = str(ULID())
    conn.execute(
        """INSERT INTO user (id, username, team_id, role, display_name, email)
           VALUES (?, ?, ?, ?, '', '')""",
        (user_id, username.lower(), team_row["id"], role),
    )
    return {
        "user_id": user_id,
        "username": username.lower(),
        "team_id": team_row["id"],
        "team_slug": team_row["slug"],
        "team_name": team_row["name"],
        "role": role,
        "display_name": "",
        "email": "",
        "archived": 0,
    }


async def require_authelia(request: Request) -> AuthContext:
    """FastAPI dependency. Raises 401/403 on auth failure, returns AuthContext on success."""
    dev_bypass = False
    # 0. Dev mode short-circuit. Bypasses proxy + Remote-User checks entirely
    # so the app can run on a developer laptop without nginx/Authelia.
    # Startup (api/main.py) refuses to boot if dev_user is set together with a
    # non-loopback host, so reaching here implies localhost-only.
    if settings.dev_user:
        username = settings.dev_user.strip().lower()
        dev_bypass = True
    else:
        # 1. Trust proxy: only nginx on loopback should reach uvicorn
        client_ip = request.client.host if request.client else ""
        if client_ip not in settings.trusted_proxy_ips_list:
            log_event("untrusted_proxy", request, detail={"client_ip": client_ip})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="request not from trusted proxy",
            )

        # 2. Remote-User header present and non-empty
        username = (request.headers.get("Remote-User") or "").strip().lower()
        if not username:
            log_event("missing_remote_user", request)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="not authenticated",
            )

    # 3. Local lookup + last_seen bump
    autoprovisioned = False
    with db.transaction() as conn:
        user = get_user_by_username(conn, username)
        if user is None:
            if settings.single_tenant_mode:
                user = _autoprovision_user(conn, username)
                autoprovisioned = True
            else:
                log_event("unknown_user", request, username_attempted=username)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="user not registered in app — contact admin",
                )
        if user["archived"]:
            log_event(
                "archived_user", request,
                username_attempted=username,
                user_id=user["user_id"],
                team_id=user["team_id"],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="user archived",
            )
        touch_last_seen(conn, user["user_id"])

    ctx = _ctx_from_user(user)
    if autoprovisioned:
        log_event(
            "user_autoprovisioned", request,
            user_id=ctx.user_id, team_id=ctx.team_id,
            username_attempted=ctx.username,
            detail={"role": ctx.role, "via": "dev_bypass" if dev_bypass else "authelia"},
        )
    if dev_bypass:
        log_event(
            "dev_bypass", request,
            user_id=ctx.user_id, team_id=ctx.team_id,
            username_attempted=ctx.username,
        )
    log_event(
        "login_success", request,
        user_id=ctx.user_id, team_id=ctx.team_id,
        username_attempted=ctx.username,
    )
    request.state.auth = ctx
    return ctx


async def require_admin(
    request: Request,
    ctx: AuthContext = Depends(require_authelia),
) -> AuthContext:
    """Dependency requiring role=admin. Members get 403 + role_denied audit event."""
    if ctx.role != "admin":
        log_event(
            "role_denied", request,
            user_id=ctx.user_id, team_id=ctx.team_id,
            username_attempted=ctx.username,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin role required",
        )
    return ctx
