"""Middleware decisions: trust proxy, Remote-User lookup, role checks, audit.

Exercise `require_authelia` + `require_admin` via the public /api/auth/me and
/api/admin/users endpoints plus a direct unit test of `client_ip_from_request`.
Audit events are inserted into `auth_event` on both success and failure paths,
so each test checks the matching row landed.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.config import settings
from api.core import db
from api.security.audit import client_ip_from_request


def _events(event: str | None = None) -> list[dict]:
    q = "SELECT * FROM auth_event"
    params: tuple = ()
    if event:
        q += " WHERE event = ?"
        params = (event,)
    q += " ORDER BY ts DESC"
    with db.connect() as conn:
        return [dict(r) for r in conn.execute(q, params)]


# =============================================================================
# Trust proxy
# =============================================================================

def test_untrusted_proxy_returns_403(tmp_env, monkeypatch, seed_users):
    """If client.host is not in trusted_proxy_ips, 403 + untrusted_proxy event.

    TestClient reports client.host == 'testclient'. We narrow the whitelist to
    only '127.0.0.1' so that host is no longer allowed.
    """
    monkeypatch.setattr(settings, "trusted_proxy_ips", "127.0.0.1")
    from api.main import create_app
    client = TestClient(create_app())
    r = client.get("/api/auth/me", headers={"Remote-User": "fer"})
    assert r.status_code == 403
    assert "trusted proxy" in r.json()["detail"]
    assert any(e["event"] == "untrusted_proxy" for e in _events())


# =============================================================================
# Remote-User handling
# =============================================================================

def test_missing_remote_user_returns_401(app_client):
    r = app_client.get("/api/auth/me")
    assert r.status_code == 401
    assert any(e["event"] == "missing_remote_user" for e in _events())


def test_empty_remote_user_returns_401(app_client):
    """Whitespace-only Remote-User is treated as absent."""
    r = app_client.get("/api/auth/me", headers={"Remote-User": "   "})
    assert r.status_code == 401
    assert any(e["event"] == "missing_remote_user" for e in _events())


def test_unknown_user_returns_403(app_client):
    r = app_client.get("/api/auth/me", headers={"Remote-User": "ghost"})
    assert r.status_code == 403
    assert "not registered" in r.json()["detail"]
    evts = [e for e in _events("unknown_user") if e["username_attempted"] == "ghost"]
    assert evts


def test_archived_user_returns_403(app_client, seed_users):
    # Archive fer manually
    fer_id = seed_users["offsec_admin"]["id"]
    with db.transaction() as conn:
        conn.execute("UPDATE user SET archived = 1 WHERE id = ?", (fer_id,))
    r = app_client.get("/api/auth/me", headers={"Remote-User": "fer"})
    assert r.status_code == 403
    assert "archived" in r.json()["detail"]
    assert any(e["event"] == "archived_user" for e in _events())


def test_case_insensitive_username(app_client, seed_users):
    """Authelia may normalize to lowercase; our lookup must too."""
    r = app_client.get("/api/auth/me", headers={"Remote-User": "FER"})
    assert r.status_code == 200
    assert r.json()["username"] == "fer"


def test_login_success_updates_last_seen(offsec_admin_client, seed_users):
    offsec_admin_client.get("/api/auth/me")
    with db.connect() as conn:
        row = conn.execute(
            "SELECT last_seen_at FROM user WHERE username = 'fer'"
        ).fetchone()
    assert row["last_seen_at"] is not None


def test_login_success_logs_audit(offsec_admin_client):
    offsec_admin_client.get("/api/auth/me")
    evts = [e for e in _events("login_success") if e["username_attempted"] == "fer"]
    assert evts


# =============================================================================
# Role-based authorization
# =============================================================================

def test_member_on_admin_endpoint_returns_403(offsec_member_client):
    r = offsec_member_client.get("/api/admin/users")
    assert r.status_code == 403
    assert "admin role required" in r.json()["detail"]
    assert any(e["event"] == "role_denied" for e in _events())


def test_admin_on_admin_endpoint_passes(offsec_admin_client):
    r = offsec_admin_client.get("/api/admin/users")
    assert r.status_code == 200


# =============================================================================
# IP parsing priority (unit — no TestClient)
# =============================================================================

class _ClientStub:
    def __init__(self, host: str) -> None:
        self.host = host


class _RequestStub:
    def __init__(self, headers: dict, client_host: str = "127.0.0.1") -> None:
        self.headers = headers
        self.client = _ClientStub(client_host)


def test_ip_parsing_prefers_x_real_ip():
    req = _RequestStub(
        headers={"X-Real-IP": "10.8.0.42", "X-Forwarded-For": "1.1.1.1, 2.2.2.2"},
    )
    assert client_ip_from_request(req) == "10.8.0.42"


def test_ip_parsing_falls_back_to_xff_first_entry():
    req = _RequestStub(headers={"X-Forwarded-For": "1.1.1.1, 2.2.2.2"})
    assert client_ip_from_request(req) == "1.1.1.1"


def test_ip_parsing_falls_back_to_client_host():
    req = _RequestStub(headers={}, client_host="127.0.0.1")
    assert client_ip_from_request(req) == "127.0.0.1"
