"""Admin endpoints: /api/admin/users (GET, POST, PATCH) + /api/admin/auth-events.

These are team-scoped — an offsec admin operates only on offsec users. Every
cross-team access returns 404 to avoid leaking existence by ID. Members are
rejected by `require_admin` before reaching any handler logic.
"""
from __future__ import annotations

from api.core import db


# =============================================================================
# /api/admin/users GET
# =============================================================================

def test_list_users_as_admin_returns_own_team_only(offsec_admin_client, seed_users):
    r = offsec_admin_client.get("/api/admin/users")
    assert r.status_code == 200
    users = r.json()
    teams = {u["team_id"] for u in users}
    assert teams == {"offsec"}
    usernames = {u["username"] for u in users}
    assert "fer" in usernames and "carlos" in usernames
    assert "ana" not in usernames and "bart" not in usernames


def test_list_users_default_hides_archived(offsec_admin_client, seed_users):
    with db.transaction() as conn:
        conn.execute("UPDATE user SET archived = 1 WHERE username = 'carlos'")
    r = offsec_admin_client.get("/api/admin/users")
    assert not any(u["username"] == "carlos" for u in r.json())

    r2 = offsec_admin_client.get("/api/admin/users?archived=true")
    assert any(u["username"] == "carlos" for u in r2.json())


def test_list_users_as_member_forbidden(offsec_member_client):
    r = offsec_member_client.get("/api/admin/users")
    assert r.status_code == 403
    assert "admin role required" in r.json()["detail"]


# =============================================================================
# /api/admin/users POST
# =============================================================================

def test_create_user_in_own_team(offsec_admin_client):
    r = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "ux_designer", "role": "member",
              "display_name": "UX", "email": "ux@test.local"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "ux_designer"
    assert body["team_id"] == "offsec"
    assert body["role"] == "member"


def test_create_user_with_matching_team_works(offsec_admin_client):
    r = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "matching", "role": "member", "team": "offsec"},
    )
    assert r.status_code == 201


def test_create_user_with_other_team_rejected(offsec_admin_client):
    r = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "crossteam", "role": "admin", "team": "infosec"},
    )
    assert r.status_code == 400
    assert "team mismatch" in r.json()["detail"]


def test_create_user_duplicate_returns_409(offsec_admin_client, seed_users):
    r = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "fer", "role": "member"},
    )
    assert r.status_code == 409


def test_create_user_normalizes_username_to_lowercase(offsec_admin_client):
    r = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "UPPER", "role": "member"},
    )
    assert r.status_code == 201
    assert r.json()["username"] == "upper"


# =============================================================================
# /api/admin/users PATCH
# =============================================================================

def test_patch_user_updates_role(offsec_admin_client, seed_users):
    carlos_id = seed_users["offsec_member"]["id"]
    r = offsec_admin_client.patch(
        f"/api/admin/users/{carlos_id}",
        json={"role": "admin"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_patch_user_archives_and_unarchives(offsec_admin_client, seed_users):
    carlos_id = seed_users["offsec_member"]["id"]
    r = offsec_admin_client.patch(
        f"/api/admin/users/{carlos_id}",
        json={"archived": True},
    )
    assert r.status_code == 200
    assert r.json()["archived"] == 1
    r = offsec_admin_client.patch(
        f"/api/admin/users/{carlos_id}",
        json={"archived": False},
    )
    assert r.json()["archived"] == 0


def test_patch_cross_team_returns_404(offsec_admin_client, seed_users):
    # ana (infosec) must appear non-existent to offsec admin
    ana_id = seed_users["infosec_admin"]["id"]
    r = offsec_admin_client.patch(
        f"/api/admin/users/{ana_id}",
        json={"role": "member"},
    )
    assert r.status_code == 404


def test_patch_empty_body_returns_400(offsec_admin_client, seed_users):
    carlos_id = seed_users["offsec_member"]["id"]
    r = offsec_admin_client.patch(
        f"/api/admin/users/{carlos_id}",
        json={},
    )
    assert r.status_code == 400


# =============================================================================
# /api/admin/auth-events
# =============================================================================

def test_auth_events_filtered_by_team(offsec_admin_client, infosec_admin_client):
    # Generate some traffic from each team
    offsec_admin_client.get("/api/people")
    infosec_admin_client.get("/api/people")

    r = offsec_admin_client.get("/api/admin/auth-events")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data and "total" in data
    teams = {e["team_id"] for e in data["events"] if e["team_id"]}
    assert teams == {"offsec"}


def test_auth_events_filter_by_event_type(offsec_admin_client):
    offsec_admin_client.get("/api/auth/me")  # login_success event
    r = offsec_admin_client.get("/api/admin/auth-events?event=login_success")
    data = r.json()
    assert data["total"] >= 1
    assert all(e["event"] == "login_success" for e in data["events"])


def test_auth_events_pagination(offsec_admin_client):
    # Generate a few requests to have ≥2 events
    for _ in range(3):
        offsec_admin_client.get("/api/auth/me")
    r = offsec_admin_client.get("/api/admin/auth-events?limit=1&offset=0")
    data = r.json()
    assert len(data["events"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 0


def test_auth_events_member_forbidden(offsec_member_client):
    r = offsec_member_client.get("/api/admin/auth-events")
    assert r.status_code == 403
