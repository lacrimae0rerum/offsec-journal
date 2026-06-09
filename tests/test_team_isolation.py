"""Cross-team isolation — the most important correctness invariant in the app.

Every tenant-scoped table must filter by `team_id`. Endpoints that return a
single resource by ID must respond 404 (not 403) when the resource exists in
a different team — otherwise the API leaks existence through the status code.

These tests seed data in both teams and verify that queries from one side
cannot observe rows from the other.
"""
from __future__ import annotations

import pytest

from api.core import db


# =============================================================================
# Helper: seed extra data in infosec (offsec already has the historic seed)
# =============================================================================

@pytest.fixture
def infosec_data(seed_users):
    """Insert one person + project + client + assignment in the infosec team.
    Returns a dict with the inserted IDs for cross-team lookups."""
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO person (id, team_id, full_name, office, city, global_level, start_date)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("spy_01", "infosec", "Spy One", "madrid", "Madrid", "senior", "2025-01-01"),
        )
        conn.execute(
            "INSERT INTO person_skill (person_id, team_id, skill_id, level) VALUES (?, ?, ?, ?)",
            ("spy_01", "infosec", "hacking_web", 4),
        )
        conn.execute(
            "INSERT INTO client (id, team_id, name, sector, status) VALUES (?, ?, ?, ?, ?)",
            ("INF-CLI-01", "infosec", "SecretClient", "gov", "activo"),
        )
        conn.execute(
            "INSERT INTO project (code, team_id, client_alias, type, window_start, window_end, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("INF-SECRET-999", "infosec", "INF-CLI-01", "audit",
             "2026-07-01", "2026-07-31", "pipeline"),
        )
        conn.execute(
            "INSERT INTO project_required_skill (project_code, team_id, skill_id, weight, min_level)"
            " VALUES (?, ?, ?, ?, ?)",
            ("INF-SECRET-999", "infosec", "hacking_web", 3, 5),
        )
        conn.execute(
            "INSERT INTO assignment (team_id, person_id, project_code, dedication_pct, start, end, role)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("infosec", "spy_01", "INF-SECRET-999", 60,
             "2026-07-01", "2026-07-31", "lead"),
        )
    return {
        "person_id": "spy_01",
        "project_code": "INF-SECRET-999",
        "client_id": "INF-CLI-01",
    }


# =============================================================================
# List endpoints never leak across teams
# =============================================================================

def test_list_people_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    off = offsec_admin_client.get("/api/people").json()
    inf = infosec_admin_client.get("/api/people").json()
    off_ids = {p["id"] for p in off}
    inf_ids = {p["id"] for p in inf}
    assert "spy_01" in inf_ids and "spy_01" not in off_ids
    assert "fer" in off_ids and "fer" not in inf_ids


def test_list_projects_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    off = offsec_admin_client.get("/api/projects").json()
    inf = infosec_admin_client.get("/api/projects").json()
    assert not any(p["code"] == "INF-SECRET-999" for p in off)
    assert any(p["code"] == "INF-SECRET-999" for p in inf)


def test_list_clients_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    off = offsec_admin_client.get("/api/clients").json()
    inf = infosec_admin_client.get("/api/clients").json()
    assert not any(c["id"] == "INF-CLI-01" for c in off)
    assert any(c["id"] == "INF-CLI-01" for c in inf)


def test_list_offices_scoped(offsec_admin_client, infosec_admin_client):
    off = offsec_admin_client.get("/api/offices").json()
    inf = infosec_admin_client.get("/api/offices").json()
    assert len(off) == 4  # madrid, barcelona, lisboa, remote
    assert len(inf) == 0


def test_skills_catalog_shared(offsec_admin_client, infosec_admin_client):
    off = offsec_admin_client.get("/api/skills").json()
    inf = infosec_admin_client.get("/api/skills").json()
    # Same 20 skills for everyone
    assert {s["id"] for s in off} == {s["id"] for s in inf}
    assert len(off) == 20


# =============================================================================
# Single-resource GET by ID returns 404 (not 403) cross-team — no enumeration
# =============================================================================

def test_get_person_cross_team_returns_404(offsec_admin_client, infosec_data):
    # spy_01 exists but in infosec; offsec admin must see 404, NOT 403
    r = offsec_admin_client.get(f"/api/people/{infosec_data['person_id']}")
    assert r.status_code == 404


def test_get_project_cross_team_returns_404(offsec_admin_client, infosec_data):
    r = offsec_admin_client.get(f"/api/projects/{infosec_data['project_code']}")
    assert r.status_code == 404


def test_get_client_cross_team_returns_404(offsec_admin_client, infosec_data):
    r = offsec_admin_client.get(f"/api/clients/{infosec_data['client_id']}")
    assert r.status_code == 404


# =============================================================================
# Aggregates scoped per team
# =============================================================================

def test_heatmap_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    q = "/api/heatmap?start=2026-07-01&end=2026-07-07"
    off = offsec_admin_client.get(q).json()
    inf = infosec_admin_client.get(q).json()
    assert "spy_01" not in off["people"]
    assert "spy_01" in inf["people"]
    assert "fer" in off["people"]
    assert "fer" not in inf["people"]


def test_skill_gap_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    # Infosec needs hacking_web L5, spy_01 has L4 -> deficit 1
    inf_gap = infosec_admin_client.get("/api/skill-gap?scope=pipeline").json()
    hw = next((g for g in inf_gap if g["skill_id"] == "hacking_web"), None)
    assert hw is not None and hw["have"] == 4 and hw["deficit"] == 1
    # Offsec's gap computation must not see the infosec project
    off_gap = offsec_admin_client.get("/api/skill-gap?scope=pipeline").json()
    assert all("INF-SECRET" not in g.get("project_code", "") for g in off_gap)


def test_coherence_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    # Offsec has the canonical insufficient_skill_coverage case (tbd_03).
    # Infosec has only spy_01 (senior with 1 skill -> also triggers the rule,
    # but as a _separate_ warning, not duplicated for offsec).
    off = offsec_admin_client.get("/api/coherence").json()
    inf = infosec_admin_client.get("/api/coherence").json()
    off_person_ids = {w["person_id"] for w in off["warnings"]}
    inf_person_ids = {w["person_id"] for w in inf["warnings"]}
    assert "spy_01" in inf_person_ids
    assert "spy_01" not in off_person_ids
    assert "tbd_03" in off_person_ids
    assert "tbd_03" not in inf_person_ids


# =============================================================================
# Search (FTS5 + LIKE) never leaks cross-team
# =============================================================================

def test_search_by_name_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    # "Spy" is unique to infosec's spy_01.full_name
    off = offsec_admin_client.get("/api/search?q=Spy").json()
    inf = infosec_admin_client.get("/api/search?q=Spy").json()
    assert not any(p["id"] == "spy_01" for p in off["people"])
    assert any(p["id"] == "spy_01" for p in inf["people"])


def test_search_by_project_code_scoped(offsec_admin_client, infosec_admin_client, infosec_data):
    off = offsec_admin_client.get("/api/search?q=INF-SECRET").json()
    inf = infosec_admin_client.get("/api/search?q=INF-SECRET").json()
    assert not any(p["code"] == "INF-SECRET-999" for p in off["projects"])
    assert any(p["code"] == "INF-SECRET-999" for p in inf["projects"])


# =============================================================================
# Admin ops: cross-team creates are rejected at the API (CLI is the escape hatch)
# =============================================================================

def test_admin_create_user_cross_team_rejected(offsec_admin_client):
    r = offsec_admin_client.post(
        "/api/admin/users",
        json={"username": "new_infosec_user", "role": "member", "team": "infosec"},
    )
    assert r.status_code == 400
    assert "team mismatch" in r.json()["detail"]


def test_admin_patch_user_cross_team_returns_404(offsec_admin_client, seed_users):
    # ana is infosec admin; offsec admin must see 404 on her ID (no enumeration)
    ana_id = seed_users["infosec_admin"]["id"]
    r = offsec_admin_client.patch(f"/api/admin/users/{ana_id}", json={"role": "member"})
    assert r.status_code == 404


# =============================================================================
# Journal entries are visible and applicable only within their team
# =============================================================================

def test_journal_entry_invisible_to_other_team(offsec_admin_client, infosec_admin_client):
    created = offsec_admin_client.post("/api/journal", json={
        "kind": "skill_update",
        "payload": {"person_id": "tbd_01", "skill_id": "osint", "level": 4},
    }).json()
    eid = created["id"]
    off_ids = [e["id"] for e in offsec_admin_client.get("/api/journal").json()]
    inf_ids = [e["id"] for e in infosec_admin_client.get("/api/journal").json()]
    assert eid in off_ids
    assert eid not in inf_ids


def test_apply_wrong_team_fails_404_style(offsec_admin_client, infosec_admin_client):
    created = offsec_admin_client.post("/api/journal", json={
        "kind": "skill_update",
        "payload": {"person_id": "tbd_01", "skill_id": "osint", "level": 4},
    }).json()
    r = infosec_admin_client.post(f"/api/journal/{created['id']}/apply")
    # The journal handler raises JournalError("entry not found in team 'infosec'")
    assert r.status_code == 400
    assert "not found" in r.json()["detail"]
