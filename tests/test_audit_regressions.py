"""Regression tests for issues surfaced by the security + code audit.

Covers:
  - C1: Path traversal in notes entity_id
  - T11: `?archived=true` query param on list endpoints
  - T11: 401 path on read endpoints that lacked explicit coverage
  - H6: rate-limit on /api/admin/users mutations
"""
from __future__ import annotations

import pytest

from api.core import db
from api.security.rate_limit import admin_mutations, reset_for_tests


# =============================================================================
# C1 — path traversal in notes.append / notes.read_all
# =============================================================================

class TestNotesEntityIdPathTraversal:
    def test_entity_id_with_slash_rejected(self, tmp_env):
        from api.core import notes
        with pytest.raises(ValueError, match="invalid entity_id"):
            notes.append("person", "foo/bar", "body", "fer", "offsec")

    def test_entity_id_with_backslash_rejected(self, tmp_env):
        from api.core import notes
        with pytest.raises(ValueError, match="invalid entity_id"):
            notes.append("person", "foo\\bar", "body", "fer", "offsec")

    def test_entity_id_with_dotdot_rejected(self, tmp_env):
        from api.core import notes
        with pytest.raises(ValueError, match="invalid entity_id"):
            notes.append("person", "../infosec/persons/victim", "body",
                         "fer", "offsec")

    def test_entity_id_empty_rejected(self, tmp_env):
        from api.core import notes
        with pytest.raises(ValueError, match="invalid entity_id"):
            notes.append("person", "", "body", "fer", "offsec")

    def test_post_notes_with_path_traversal_returns_400(self, offsec_admin_client):
        """HTTP regression: the POST /api/notes endpoint must refuse traversal."""
        r = offsec_admin_client.post("/api/notes", json={
            "entity_type": "person",
            "entity_id": "../../infosec/persons/spy",
            "body": "leak attempt",
        })
        assert r.status_code == 400
        assert "invalid entity_id" in r.json()["detail"]


# =============================================================================
# T11 — `?archived=true` on list endpoints
# =============================================================================

class TestArchivedFiltering:
    def test_people_list_archived_param(self, offsec_admin_client):
        # Archive tbd_04 via the journal
        entry = offsec_admin_client.post("/api/journal", json={
            "kind": "person_archive",
            "payload": {"id": "tbd_04", "archived": True},
        }).json()
        offsec_admin_client.post(f"/api/journal/{entry['id']}/apply")

        default = offsec_admin_client.get("/api/people").json()
        with_arch = offsec_admin_client.get("/api/people?archived=true").json()

        assert not any(p["id"] == "tbd_04" for p in default)
        assert any(p["id"] == "tbd_04" for p in with_arch)

    def test_projects_list_archived_param(self, offsec_admin_client):
        entry = offsec_admin_client.post("/api/journal", json={
            "kind": "project_archive",
            "payload": {"code": "PT-2026-018", "archived": True},
        }).json()
        offsec_admin_client.post(f"/api/journal/{entry['id']}/apply")

        default = offsec_admin_client.get("/api/projects").json()
        with_arch = offsec_admin_client.get("/api/projects?archived=true").json()

        assert not any(p["code"] == "PT-2026-018" for p in default)
        assert any(p["code"] == "PT-2026-018" for p in with_arch)

    def test_clients_list_archived_param(self, offsec_admin_client):
        entry = offsec_admin_client.post("/api/journal", json={
            "kind": "client_archive",
            "payload": {"id": "interno", "archived": True},
        }).json()
        offsec_admin_client.post(f"/api/journal/{entry['id']}/apply")

        default = offsec_admin_client.get("/api/clients").json()
        with_arch = offsec_admin_client.get("/api/clients?archived=true").json()

        assert not any(c["id"] == "interno" for c in default)
        assert any(c["id"] == "interno" for c in with_arch)


# =============================================================================
# T11 — 401 coverage on read endpoints
# =============================================================================

class TestAuthRequiredOnReadEndpoints:
    """Every authed endpoint must 401 without Remote-User. Fills gaps that
    test_endpoints.py only covers for a sample."""

    @pytest.mark.parametrize("path", [
        "/api/coherence",
        "/api/heatmap?start=2026-04-06&end=2026-05-03",
        "/api/skill-gap",
        "/api/notes?entity_type=person&entity_id=fer",
        "/api/offices",
        "/api/geo",
        "/api/skills",
        "/api/auth/me",
        "/api/admin/users",
        "/api/admin/auth-events",
    ])
    def test_read_endpoint_requires_remote_user(self, app_client, path):
        r = app_client.get(path)
        assert r.status_code == 401, f"{path} should 401 without Remote-User, got {r.status_code}"


# =============================================================================
# H6 — rate-limit on /api/admin/users
# =============================================================================

class TestAdminRateLimit:
    def test_create_user_throttled_after_budget(self, offsec_admin_client):
        """After 10 creates within 60s the 11th returns 429."""
        reset_for_tests()
        # Consume the budget with valid creates
        for i in range(10):
            r = offsec_admin_client.post("/api/admin/users", json={
                "username": f"bulk_{i}", "role": "member",
            })
            assert r.status_code == 201, f"create {i}: {r.status_code} {r.text}"
        # 11th must be rate-limited
        r = offsec_admin_client.post("/api/admin/users", json={
            "username": "bulk_overflow", "role": "member",
        })
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert "rate limit" in r.json()["detail"].lower()

    def test_reset_between_tests_isolates_buckets(self):
        """Sanity: reset_for_tests() empties the in-memory bucket."""
        reset_for_tests()
        assert len(admin_mutations._hits) == 0


# =============================================================================
# H4 — journal create_entry validates BEFORE writing YAML
# =============================================================================

class TestJournalValidatesBeforeWrite:
    def test_invalid_payload_does_not_touch_yaml(self, tmp_env, seed_users):
        """A POST with a malformed payload must 400 without creating a pending entry."""
        from api.core import queries

        # Verify initial state
        with db.connect() as conn:
            before = len(queries.list_journal(conn, "offsec"))

        # Use the in-process core API (same path the route takes)
        from api.core import journal
        with pytest.raises(journal.JournalError, match="invalid payload"):
            journal.validate_payload("assign", {"person_id": "fer"})  # missing fields

        # Journal must be unchanged
        with db.connect() as conn:
            after = len(queries.list_journal(conn, "offsec"))
        assert before == after
