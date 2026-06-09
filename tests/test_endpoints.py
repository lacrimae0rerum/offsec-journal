"""Integration tests against the FastAPI app via TestClient.

One test per endpoint. Auth guard checked for each authed route. Shape
assertions are intentionally narrow (check the keys the frontend reads, not
every field) so adding new optional fields doesn't break tests.

All authed tests use `offsec_admin_client` (from conftest), which preloads
`Remote-User: fer` + `X-Real-IP` — simulating what nginx would inject after
forward-auth against Authelia.
"""
from __future__ import annotations


# ---------- health + auth gate ----------
def test_health_unauthed(app_client):
    r = app_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_authed_endpoints_reject_missing_remote_user(app_client):
    """Without the Remote-User header (what nginx injects), the middleware 401s."""
    for path in ["/api/people", "/api/projects", "/api/journal", "/api/search?q=x"]:
        r = app_client.get(path)
        assert r.status_code == 401, f"{path} should 401 without Remote-User"


def test_authed_endpoints_reject_unknown_user(app_client):
    """User authenticated in Authelia but not registered in the app table -> 403."""
    r = app_client.get("/api/people", headers={"Remote-User": "ghost"})
    assert r.status_code == 403
    assert "not registered" in r.json()["detail"]


# ---------- people ----------
def test_list_people(offsec_admin_client):
    r = offsec_admin_client.get("/api/people")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 6
    fer = next(p for p in data if p["id"] == "fer")
    assert set(["id", "full_name", "office", "global_level", "skills"]) <= set(fer.keys())
    assert isinstance(fer["skills"], list)
    assert len(fer["skills"]) == 7


def test_get_person(offsec_admin_client):
    r = offsec_admin_client.get("/api/people/fer")
    assert r.status_code == 200
    p = r.json()
    assert p["full_name"] == "Alex P."
    assert "assignments" in p
    assert "availability" in p


def test_get_person_404(offsec_admin_client):
    r = offsec_admin_client.get("/api/people/does_not_exist")
    assert r.status_code == 404


def test_person_coherence(offsec_admin_client):
    r = offsec_admin_client.get("/api/people/fer/coherence")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True  # fer is a clean senior
    assert data["warnings"] == []


def test_person_coherence_warning(offsec_admin_client):
    r = offsec_admin_client.get("/api/people/tbd_03/coherence")
    data = r.json()
    assert data["ok"] is False
    assert any(w["rule"] == "insufficient_skill_coverage" for w in data["warnings"])


# ---------- projects ----------
def test_list_projects(offsec_admin_client):
    r = offsec_admin_client.get("/api/projects")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 8
    codes = {p["code"] for p in data}
    assert "PT-2026-018" in codes


def test_list_projects_filtered_by_status(offsec_admin_client):
    r = offsec_admin_client.get("/api/projects?status=pipeline")
    assert all(p["status"] == "pipeline" for p in r.json())


def test_get_project(offsec_admin_client):
    r = offsec_admin_client.get("/api/projects/PT-2026-018")
    p = r.json()
    assert p["client_alias"] == "alfa"
    assert len(p["required_skills"]) >= 1


# ---------- clients ----------
def test_list_clients(offsec_admin_client):
    r = offsec_admin_client.get("/api/clients")
    data = r.json()
    assert len(data) == 8
    alfa = next(c for c in data if c["id"] == "alfa")
    assert len(alfa["contacts"]) == 2
    assert any(p["code"] == "PT-2026-018" for p in alfa["projects"])


def test_get_client(offsec_admin_client):
    r = offsec_admin_client.get("/api/clients/alfa")
    assert r.status_code == 200
    assert r.json()["name"] == "Cliente Alfa"


# ---------- skills / offices / geo ----------
def test_list_skills(offsec_admin_client):
    r = offsec_admin_client.get("/api/skills")
    data = r.json()
    assert len(data) == 20
    assert all("label_es" in s for s in data)


def test_list_offices(offsec_admin_client):
    r = offsec_admin_client.get("/api/offices")
    data = r.json()
    ids = {o["office_id"] for o in data}
    assert {"madrid", "barcelona", "lisboa", "remote"} <= ids


def test_geo_has_people(offsec_admin_client):
    r = offsec_admin_client.get("/api/geo")
    data = r.json()
    madrid = next(o for o in data if o["office_id"] == "madrid")
    assert "fer" in madrid["people"]
    assert "santi" in madrid["people"]


# ---------- coherence ----------
def test_coherence_global(offsec_admin_client):
    r = offsec_admin_client.get("/api/coherence")
    data = r.json()
    assert "warnings" in data
    assert data["count"] == len(data["warnings"])
    assert any(
        w["person_id"] == "tbd_03" and w["rule"] == "insufficient_skill_coverage"
        for w in data["warnings"]
    )


# ---------- heatmap ----------
def test_heatmap_basic(offsec_admin_client):
    r = offsec_admin_client.get("/api/heatmap?start=2026-04-06&end=2026-05-03")
    assert r.status_code == 200
    data = r.json()
    assert data["weeks"] == ["2026-W15", "2026-W16", "2026-W17", "2026-W18"]
    assert "fer" in data["people"]
    assert len(data["people"]["fer"]) == 4


def test_heatmap_bad_date(offsec_admin_client):
    r = offsec_admin_client.get("/api/heatmap?start=nope&end=2026-05-03")
    assert r.status_code == 400


def test_heatmap_start_after_end(offsec_admin_client):
    r = offsec_admin_client.get("/api/heatmap?start=2026-05-03&end=2026-04-06")
    assert r.status_code == 400


# ---------- skill gap ----------
def test_skill_gap_pipeline(offsec_admin_client):
    r = offsec_admin_client.get("/api/skill-gap?scope=pipeline")
    assert r.status_code == 200
    data = r.json()
    cloud = next((g for g in data if g["skill_id"] == "hacking_cloud"), None)
    assert cloud is not None
    assert cloud["deficit"] >= 1


# ---------- search ----------
def test_search_empty_query(offsec_admin_client):
    r = offsec_admin_client.get("/api/search?q=")
    data = r.json()
    assert data["stats"]["total"] == 0


def test_search_person(offsec_admin_client):
    r = offsec_admin_client.get("/api/search?q=fer")
    data = r.json()
    assert any(p["id"] == "fer" for p in data["people"])


def test_search_project(offsec_admin_client):
    r = offsec_admin_client.get("/api/search?q=PT-2026")
    data = r.json()
    assert any(p["code"].startswith("PT-2026") for p in data["projects"])


# ---------- journal ----------
def test_list_journal(offsec_admin_client):
    r = offsec_admin_client.get("/api/journal")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3


def test_journal_filter_pending(offsec_admin_client):
    r = offsec_admin_client.get("/api/journal?status=pending")
    data = r.json()
    assert all(e["status"] == "pending" for e in data)


def test_create_journal_entry(offsec_admin_client):
    body = {
        "kind": "skill_update",
        "payload": {"person_id": "tbd_01", "skill_id": "osint", "level": 3},
    }
    r = offsec_admin_client.post("/api/journal", json=body)
    assert r.status_code == 200, r.text
    entry = r.json()
    assert entry["status"] == "pending"
    assert entry["proposer"] == "human"
    assert len(entry["id"]) == 26  # ULID
    # created_by_user_id se popula con ctx.user_id — ULID también
    assert entry["created_by_user_id"] is not None


def test_apply_reject_full_cycle(offsec_admin_client):
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
    created = offsec_admin_client.post("/api/journal", json=body).json()
    r = offsec_admin_client.post(f"/api/journal/{created['id']}/apply")
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    project = offsec_admin_client.get("/api/projects/RES-2026-001").json()
    assert any(a["person_id"] == "tbd_04" for a in project["assignments"])


def test_reject_requires_reason(offsec_admin_client):
    body = {
        "kind": "skill_update",
        "payload": {"person_id": "tbd_01", "skill_id": "osint", "level": 3},
    }
    created = offsec_admin_client.post("/api/journal", json=body).json()
    r = offsec_admin_client.post(f"/api/journal/{created['id']}/reject", json={"reason": ""})
    assert r.status_code == 400


def test_reject_happy_path(offsec_admin_client):
    body = {
        "kind": "skill_update",
        "payload": {"person_id": "tbd_01", "skill_id": "osint", "level": 3},
    }
    created = offsec_admin_client.post("/api/journal", json=body).json()
    r = offsec_admin_client.post(
        f"/api/journal/{created['id']}/reject",
        json={"reason": "pending PM confirmation"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert r.json()["rejected_reason"] == "pending PM confirmation"


def test_apply_nonexistent_fails(offsec_admin_client):
    r = offsec_admin_client.post("/api/journal/01FAKE0000000000000000AAAA/apply")
    assert r.status_code == 400


# ---------- notes ----------
def test_notes_read_existing(offsec_admin_client):
    r = offsec_admin_client.get("/api/notes?entity_type=person&entity_id=fer")
    data = r.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert all({"timestamp", "author", "tags", "body"} <= set(n.keys()) for n in data)


def test_notes_append(offsec_admin_client):
    body = {
        "entity_type": "person",
        "entity_id": "santi",
        "body": "nota de integración test",
        "tags": ["testing"],
    }
    r = offsec_admin_client.post("/api/notes", json=body)
    assert r.status_code == 200
    note = r.json()
    # Backend fills author from ctx.username when body.author is default "human"
    assert note["author"] in ("fer", "pytest")
    listed = offsec_admin_client.get(
        "/api/notes?entity_type=person&entity_id=santi"
    ).json()
    assert any("nota de integración test" in n["body"] for n in listed)


def test_notes_rejects_empty_body(offsec_admin_client):
    r = offsec_admin_client.post(
        "/api/notes",
        json={"entity_type": "project", "entity_id": "PT-2026-018", "body": "   "},
    )
    assert r.status_code == 400
