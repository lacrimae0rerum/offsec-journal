"""Integration tests against the FastAPI app via TestClient.

One test per endpoint. Auth guard checked for each authed route. Shape assertions
are intentionally narrow (check the keys the frontend reads, not every field) so
that adding new optional fields doesn't break tests.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.main import create_app


@pytest.fixture
def client(tmp_env):
    # tmp_env already set data_dir/db_path on settings; recreate the app so
    # routers wire against the fresh state.
    app = create_app()
    return TestClient(app)


@pytest.fixture
def headers():
    return {"X-API-Key": settings.api_key}


# ---------- health + auth ----------
def test_health_unauthed(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_authed_endpoints_reject_missing_key(client):
    # Sample a handful — full matrix would be noise
    for path in ["/api/people", "/api/projects", "/api/journal", "/api/search?q=x"]:
        r = client.get(path)
        assert r.status_code == 401, f"{path} should require key"


def test_authed_endpoints_reject_wrong_key(client):
    r = client.get("/api/people", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


# ---------- people ----------
def test_list_people(client, headers):
    r = client.get("/api/people", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 6
    fer = next(p for p in data if p["id"] == "fer")
    assert set(["id", "full_name", "office", "global_level", "skills"]) <= set(fer.keys())
    assert isinstance(fer["skills"], list)
    assert len(fer["skills"]) == 7


def test_get_person(client, headers):
    r = client.get("/api/people/fer", headers=headers)
    assert r.status_code == 200
    p = r.json()
    assert p["full_name"] == "Alex P."
    assert "assignments" in p
    assert "availability" in p


def test_get_person_404(client, headers):
    r = client.get("/api/people/does_not_exist", headers=headers)
    assert r.status_code == 404


def test_person_coherence(client, headers):
    r = client.get("/api/people/fer/coherence", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True  # fer is a clean senior
    assert data["warnings"] == []


def test_person_coherence_warning(client, headers):
    r = client.get("/api/people/tbd_03/coherence", headers=headers)
    data = r.json()
    assert data["ok"] is False
    assert any(w["rule"] == "insufficient_skill_coverage" for w in data["warnings"])


# ---------- projects ----------
def test_list_projects(client, headers):
    r = client.get("/api/projects", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 8
    codes = {p["code"] for p in data}
    assert "PT-2026-018" in codes


def test_list_projects_filtered_by_status(client, headers):
    r = client.get("/api/projects?status=pipeline", headers=headers)
    assert all(p["status"] == "pipeline" for p in r.json())


def test_get_project(client, headers):
    r = client.get("/api/projects/PT-2026-018", headers=headers)
    p = r.json()
    assert p["client_alias"] == "alfa"
    assert len(p["required_skills"]) >= 1


# ---------- clients ----------
def test_list_clients(client, headers):
    r = client.get("/api/clients", headers=headers)
    data = r.json()
    assert len(data) == 8
    alfa = next(c for c in data if c["id"] == "alfa")
    assert len(alfa["contacts"]) == 2
    assert any(p["code"] == "PT-2026-018" for p in alfa["projects"])


def test_get_client(client, headers):
    r = client.get("/api/clients/alfa", headers=headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Cliente Alfa"


# ---------- skills / offices / geo ----------
def test_list_skills(client, headers):
    r = client.get("/api/skills", headers=headers)
    data = r.json()
    assert len(data) == 20
    assert all("label_es" in s for s in data)


def test_list_offices(client, headers):
    r = client.get("/api/offices", headers=headers)
    data = r.json()
    ids = {o["office_id"] for o in data}
    assert {"madrid", "barcelona", "lisboa", "remote"} <= ids


def test_geo_has_people(client, headers):
    r = client.get("/api/geo", headers=headers)
    data = r.json()
    madrid = next(o for o in data if o["office_id"] == "madrid")
    assert "fer" in madrid["people"]
    assert "santi" in madrid["people"]


# ---------- coherence ----------
def test_coherence_global(client, headers):
    r = client.get("/api/coherence", headers=headers)
    data = r.json()
    assert "warnings" in data
    assert data["count"] == len(data["warnings"])
    # tbd_03 is the canonical insufficient_skill_coverage case in the seed
    assert any(
        w["person_id"] == "tbd_03" and w["rule"] == "insufficient_skill_coverage"
        for w in data["warnings"]
    )


# ---------- heatmap ----------
def test_heatmap_basic(client, headers):
    r = client.get("/api/heatmap?start=2026-04-06&end=2026-05-03", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["weeks"] == ["2026-W15", "2026-W16", "2026-W17", "2026-W18"]
    assert "fer" in data["people"]
    assert len(data["people"]["fer"]) == 4


def test_heatmap_bad_date(client, headers):
    r = client.get("/api/heatmap?start=nope&end=2026-05-03", headers=headers)
    assert r.status_code == 400


def test_heatmap_start_after_end(client, headers):
    r = client.get("/api/heatmap?start=2026-05-03&end=2026-04-06", headers=headers)
    assert r.status_code == 400


# ---------- skill gap ----------
def test_skill_gap_pipeline(client, headers):
    r = client.get("/api/skill-gap?scope=pipeline", headers=headers)
    assert r.status_code == 200
    data = r.json()
    # Pipeline has hacking_cloud requirement; our best is fer L2 vs need L3
    cloud = next((g for g in data if g["skill_id"] == "hacking_cloud"), None)
    assert cloud is not None
    assert cloud["deficit"] >= 1


# ---------- search ----------
def test_search_empty_query(client, headers):
    r = client.get("/api/search?q=", headers=headers)
    data = r.json()
    assert data["stats"]["total"] == 0


def test_search_person(client, headers):
    r = client.get("/api/search?q=fer", headers=headers)
    data = r.json()
    assert any(p["id"] == "fer" for p in data["people"])


def test_search_project(client, headers):
    r = client.get("/api/search?q=PT-2026", headers=headers)
    data = r.json()
    assert any(p["code"].startswith("PT-2026") for p in data["projects"])


# ---------- journal ----------
def test_list_journal(client, headers):
    r = client.get("/api/journal", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3


def test_journal_filter_pending(client, headers):
    r = client.get("/api/journal?status=pending", headers=headers)
    data = r.json()
    assert all(e["status"] == "pending" for e in data)


def test_create_journal_entry(client, headers):
    body = {
        "kind": "skill_update",
        "payload": {
            "person_id": "tbd_01",
            "skill_id": "osint",
            "level": 3,
            "rationale": "test",
        },
    }
    r = client.post("/api/journal", json=body, headers=headers)
    assert r.status_code == 200, r.text
    entry = r.json()
    assert entry["status"] == "pending"
    assert entry["proposer"] == "human"
    assert len(entry["id"]) == 26  # ULID


def test_apply_reject_full_cycle(client, headers):
    # Create → apply → verify
    body = {
        "kind": "assign",
        "payload": {
            "person_id": "tbd_04",
            "project_code": "RES-2026-001",
            "dedication_pct": 20,
            "start": "2026-06-15",
            "end": "2026-06-22",
            "role": "shadow",
        },
    }
    created = client.post("/api/journal", json=body, headers=headers).json()
    r = client.post(f"/api/journal/{created['id']}/apply", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    # Verify it shows up on the project
    project = client.get("/api/projects/RES-2026-001", headers=headers).json()
    assert any(a["person_id"] == "tbd_04" for a in project["assignments"])


def test_reject_requires_reason(client, headers):
    body = {"kind": "skill_update", "payload": {"person_id": "tbd_01", "skill_id": "osint", "level": 3}}
    created = client.post("/api/journal", json=body, headers=headers).json()
    r = client.post(f"/api/journal/{created['id']}/reject", json={"reason": ""}, headers=headers)
    assert r.status_code == 400


def test_reject_happy_path(client, headers):
    body = {"kind": "skill_update", "payload": {"person_id": "tbd_01", "skill_id": "osint", "level": 3}}
    created = client.post("/api/journal", json=body, headers=headers).json()
    r = client.post(
        f"/api/journal/{created['id']}/reject",
        json={"reason": "pending PM confirmation"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["rejected_reason"] == "pending PM confirmation"


def test_apply_nonexistent_fails(client, headers):
    r = client.post("/api/journal/01FAKE0000000000000000AAAA/apply", headers=headers)
    assert r.status_code == 400


# ---------- notes ----------
def test_notes_read_existing(client, headers):
    r = client.get("/api/notes?entity_type=person&entity_id=fer", headers=headers)
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all({"timestamp", "author", "tags", "body"} <= set(n.keys()) for n in data)


def test_notes_append(client, headers):
    body = {
        "entity_type": "person",
        "entity_id": "santi",
        "body": "nota de integración test",
        "author": "pytest",
        "tags": ["testing"],
    }
    r = client.post("/api/notes", json=body, headers=headers)
    assert r.status_code == 200
    note = r.json()
    assert note["author"] == "pytest"
    # verify persisted
    listed = client.get("/api/notes?entity_type=person&entity_id=santi", headers=headers).json()
    assert any("nota de integración test" in n["body"] for n in listed)


def test_notes_rejects_empty_body(client, headers):
    r = client.post(
        "/api/notes",
        json={"entity_type": "project", "entity_id": "PT-2026-018", "body": "   "},
        headers=headers,
    )
    assert r.status_code == 400
