"""Contract tests for the Admin UI -> backend boundary.

The Admin UI (web/app.js: loadAdminPage, _renderUsersTable, loadAuthEvents,
_renderAuthEventsTable) reads specific fields off these endpoints. These tests
lock the *shape* the frontend depends on, so a backend change that drops a
field the UI renders fails here loudly instead of silently rendering blanks.

This is the UI-facing complement to test_admin_endpoints.py (which exercises
team-scoping and access-control semantics). Here we assert the response
contracts the JS render functions consume.
"""
from __future__ import annotations

from api.core import db


# Fields _renderUsersTable() reads off each user row.
USER_FIELDS_RENDERED = {"id", "username", "display_name", "email", "role", "archived"}

# Fields _renderAuthEventsTable() reads off each event row.
EVENT_FIELDS_RENDERED = {
    "ts", "event", "username_attempted", "ip", "path", "detail",
}


# =============================================================================
# Users — list (GET /api/admin/users)
# =============================================================================

def test_list_users_returns_fields_the_table_renders(offsec_admin_client, seed_users):
    """_renderUsersTable needs id/username/display_name/email/role/archived."""
    response = offsec_admin_client.get("/api/admin/users")
    assert response.status_code == 200
    users = response.json()
    assert users, "expected at least the seeded offsec users"
    for user in users:
        assert USER_FIELDS_RENDERED <= user.keys(), (
            f"user row missing fields the UI renders: "
            f"{USER_FIELDS_RENDERED - user.keys()}"
        )


def test_list_users_archived_flag_includes_archived(offsec_admin_client, seed_users):
    """The 'Mostrar archivados' toggle drives adminListUsers(true)."""
    with db.transaction() as conn:
        conn.execute("UPDATE user SET archived = 1 WHERE username = 'carlos'")

    without_archived = offsec_admin_client.get("/api/admin/users").json()
    assert not any(u["username"] == "carlos" for u in without_archived)

    with_archived = offsec_admin_client.get("/api/admin/users?archived=true").json()
    assert any(u["username"] == "carlos" for u in with_archived)


# =============================================================================
# Users — create (POST /api/admin/users)
# =============================================================================

def test_create_user_returns_201_with_created_row(offsec_admin_client):
    """wireUserCreateModal reads the created user back; assert the shape."""
    response = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "newbie", "role": "member",
              "display_name": "New Bie", "email": "newbie@test.local"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newbie"
    assert body["role"] == "member"
    assert body["archived"] is False


def test_create_user_empty_username_is_rejected(offsec_admin_client):
    """Client validates first, but the backend must also reject empty username
    (defence in depth). Pydantic min_length=1 -> 422; explicit guard -> 400."""
    response = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "", "role": "member"},
    )
    assert response.status_code in (400, 422)


def test_create_user_duplicate_returns_409(offsec_admin_client, seed_users):
    """_adminError maps 409 -> 'Ya existe o hay un conflicto...'."""
    response = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "fer", "role": "member"},
    )
    assert response.status_code == 409


# =============================================================================
# Users — patch (PATCH /api/admin/users/{id})
# =============================================================================

def test_patch_user_role_returns_updated_row(offsec_admin_client, seed_users):
    """wireUserActions sends {role:'admin'} and reloads; assert it sticks."""
    carlos_id = seed_users["offsec_member"]["id"]
    response = offsec_admin_client.patch(
        f"/api/admin/users/{carlos_id}",
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_patch_user_archive_returns_updated_row(offsec_admin_client, seed_users):
    """The archive action sends {archived:true}."""
    carlos_id = seed_users["offsec_member"]["id"]
    response = offsec_admin_client.patch(
        f"/api/admin/users/{carlos_id}",
        json={"archived": True},
    )
    assert response.status_code == 200
    assert response.json()["archived"] == 1


def test_patch_cross_team_user_returns_404(offsec_admin_client, seed_users):
    """_adminError maps 404 -> 'El elemento ya no existe.'. Cross-team must 404
    (not 403) so existence isn't leaked by ID."""
    ana_id = seed_users["infosec_admin"]["id"]
    response = offsec_admin_client.patch(
        f"/api/admin/users/{ana_id}",
        json={"role": "member"},
    )
    assert response.status_code == 404


# =============================================================================
# Auth-events (GET /api/admin/auth-events)
# =============================================================================

def test_auth_events_pagination_envelope(offsec_admin_client):
    """loadAuthEvents reads events/total/limit/offset to drive prev/next."""
    for _ in range(3):
        offsec_admin_client.get("/api/auth/me")

    response = offsec_admin_client.get("/api/admin/auth-events?limit=1&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert {"events", "total", "limit", "offset"} <= data.keys()
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert len(data["events"]) <= 1
    for event in data["events"]:
        assert EVENT_FIELDS_RENDERED <= event.keys(), (
            f"event row missing fields the UI renders: "
            f"{EVENT_FIELDS_RENDERED - event.keys()}"
        )


def test_auth_events_filter_by_event_type(offsec_admin_client):
    """The #admin-event-filter select passes ?event=<type>."""
    offsec_admin_client.get("/api/auth/me")  # emits a login_success event
    response = offsec_admin_client.get(
        "/api/admin/auth-events?event=login_success"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(e["event"] == "login_success" for e in data["events"])


# =============================================================================
# Access control — the 403 path the UI renders as an in-section notice
# =============================================================================

def test_non_admin_users_endpoint_returns_403(offsec_member_client):
    """loadAdminPage catches 403 and shows 'requiere rol admin' in-section."""
    response = offsec_member_client.get("/api/admin/users")
    assert response.status_code == 403


def test_non_admin_auth_events_endpoint_returns_403(offsec_member_client):
    response = offsec_member_client.get("/api/admin/auth-events")
    assert response.status_code == 403
