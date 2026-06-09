"""Audit log of middleware decisions. Inserts rows into auth_event table.

Called from api/security/authelia.py for every decision (both successes and
failures). Never raises — audit failures are logged with loguru and swallowed,
we don't want auth to fail because the audit got full.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from loguru import logger
from ulid import ULID

from api.core import db


def client_ip_from_request(request: Request) -> str:
    """Parse the real client IP.

    Preference: X-Real-IP > X-Forwarded-For[0] > request.client.host.

    uvicorn runs without --proxy-headers intentionally, so
    request.client.host is the TCP peer (nginx on 127.0.0.1). The real client
    IP is the one nginx injected from $remote_addr / $proxy_add_x_forwarded_for.
    """
    real_ip = (request.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip
    xff = (request.headers.get("X-Forwarded-For") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else ""


def user_agent_from_request(request: Request) -> str:
    """Capped at 500 chars to avoid log bloat."""
    return (request.headers.get("User-Agent") or "")[:500]


def log_event(
    event: str,
    request: Request,
    *,
    user_id: str | None = None,
    team_id: str | None = None,
    username_attempted: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append a row to auth_event. Never raises."""
    try:
        event_id = str(ULID())
        ip = client_ip_from_request(request)
        ua = user_agent_from_request(request)
        path = request.url.path if request.url else ""
        detail_json = json.dumps(detail, ensure_ascii=False) if detail else None
        with db.transaction() as conn:
            conn.execute(
                """INSERT INTO auth_event
                      (id, event, user_id, team_id, username_attempted,
                       ip, user_agent, path, detail)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, event, user_id, team_id, username_attempted,
                 ip, ua, path, detail_json),
            )
    except Exception as e:
        logger.warning("audit log_event failed for event={}: {}", event, e)
