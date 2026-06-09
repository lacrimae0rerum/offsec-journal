"""Admin-only endpoints for user + audit management, team-scoped.

Admin de offsec NO puede gestionar users de infosec (y viceversa). Para ops
cross-team existe el CLI `offsec users ...` en el servidor.

Rules:
  - Cross-team user access -> 404 (not 403) to avoid leaking existence by ID
  - POST with team != ctx.team_slug -> 400 "team mismatch"
  - Duplicate username -> 409
  - auth-events are filtered strictly by team (NULL team_id events — from
    unknown_user / untrusted_proxy — are sysadmin-only, visible via CLI)
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from ulid import ULID

from api.core import db
from api.security import AuthContext, log_event, require_admin
from api.security.rate_limit import admin_mutations

router = APIRouter(prefix="/admin", tags=["admin"])


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    role: Literal["admin", "member"]
    team: str | None = None  # if present, must match ctx.team_slug
    display_name: str = ""
    email: str = ""


class UserUpdate(BaseModel):
    role: Literal["admin", "member"] | None = None
    archived: bool | None = None


# ============================================================
# Users
# ============================================================

@router.get("/users")
async def list_users(
    archived: bool = False,
    ctx: AuthContext = Depends(require_admin),
) -> list[dict]:
    q = """SELECT id, username, team_id, role, display_name, email,
                   archived, created_at, updated_at, last_seen_at
            FROM user WHERE team_id = ?"""
    params: list = [ctx.team_id]
    if not archived:
        q += " AND archived = 0"
    q += " ORDER BY username"
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(q, tuple(params))]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    request: Request,
    ctx: AuthContext = Depends(require_admin),
) -> dict[str, Any]:
    # Rate-limit per-admin to deter runaway scripts; bucket is in-memory and
    # resets per process. 10 creates/minute is generous for real admin work.
    admin_mutations.check(ctx.user_id)

    username = body.username.strip().lower()
    if not username:
        raise HTTPException(400, "username cannot be empty")

    # Reject cross-team attempts explicitly
    if body.team is not None and body.team != ctx.team_slug:
        log_event(
            "team_mismatch", request,
            user_id=ctx.user_id, team_id=ctx.team_id,
            username_attempted=username,
            detail={"attempted_team": body.team, "actor_team": ctx.team_slug},
        )
        raise HTTPException(
            400,
            f"team mismatch: admins can only create users in their own team "
            f"({ctx.team_slug}). Use the CLI on the server for cross-team ops.",
        )

    with db.transaction() as conn:
        existing = conn.execute(
            "SELECT team_id FROM user WHERE username = ?",
            (username,),
        ).fetchone()
        if existing is not None:
            raise HTTPException(409, f"user '{username}' already exists")

        user_id = str(ULID())
        conn.execute(
            """INSERT INTO user (id, username, team_id, role, display_name, email)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, ctx.team_id, body.role,
             body.display_name, body.email),
        )

    return {
        "id": user_id,
        "username": username,
        "team_id": ctx.team_id,
        "role": body.role,
        "display_name": body.display_name,
        "email": body.email,
        "archived": False,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdate,
    ctx: AuthContext = Depends(require_admin),
) -> dict[str, Any]:
    admin_mutations.check(ctx.user_id)
    if body.role is None and body.archived is None:
        raise HTTPException(400, "no fields to update (role or archived)")

    with db.transaction() as conn:
        # Fetch only within the admin's team — cross-team returns 404
        existing = conn.execute(
            "SELECT id, team_id FROM user WHERE id = ? AND team_id = ?",
            (user_id, ctx.team_id),
        ).fetchone()
        if existing is None:
            raise HTTPException(404, "user not found")

        updates: list[str] = []
        params: list = []
        if body.role is not None:
            updates.append("role = ?")
            params.append(body.role)
        if body.archived is not None:
            updates.append("archived = ?")
            params.append(1 if body.archived else 0)
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(user_id)
        conn.execute(
            f"UPDATE user SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )

        row = conn.execute(
            """SELECT id, username, team_id, role, display_name, email,
                      archived, last_seen_at
               FROM user WHERE id = ?""",
            (user_id,),
        ).fetchone()
    return dict(row)


# ============================================================
# Audit events
# ============================================================

@router.get("/auth-events")
async def list_auth_events(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    event: str | None = None,
    ctx: AuthContext = Depends(require_admin),
) -> dict[str, Any]:
    where = ["team_id = ?"]
    params: list = [ctx.team_id]
    if event:
        where.append("event = ?")
        params.append(event)
    where_clause = " AND ".join(where)

    list_q = (
        "SELECT id, ts, event, user_id, username_attempted, team_id, "
        "ip, user_agent, path, detail "
        f"FROM auth_event WHERE {where_clause} "
        "ORDER BY ts DESC LIMIT ? OFFSET ?"
    )
    list_params = (*params, limit, offset)
    count_q = f"SELECT COUNT(*) AS n FROM auth_event WHERE {where_clause}"

    with db.connect() as conn:
        events = [dict(r) for r in conn.execute(list_q, list_params)]
        total = conn.execute(count_q, tuple(params)).fetchone()["n"]

    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
