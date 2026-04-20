"""One test per journal handler (20 kinds). Covers the full discriminated union.

Each test: create pending entry → apply → verify the right YAML/row changed.
Avoids the TestClient layer — exercises api.core.journal directly for speed.
"""
from __future__ import annotations

from api.core import db, journal, yaml_io
from api.config import settings


def _apply(kind, payload):
    entry = journal.create_entry(kind, payload, proposer="human")
    journal.apply_entry(entry["id"], applied_by="test")
    return entry


# ---------- assign / unassign ----------
def test_handler_assign(tmp_env):
    _apply("assign", {
        "person_id": "tbd_02", "project_code": "RES-2026-001",
        "dedication_pct": 30, "start": "2026-06-10", "end": "2026-06-20", "role": "executor",
    })
    with db.transaction() as conn:
        r = conn.execute(
            "SELECT * FROM assignment WHERE person_id='tbd_02' AND project_code='RES-2026-001' AND archived=0"
        ).fetchone()
    assert r is not None
    assert r["dedication_pct"] == 30


def test_handler_unassign(tmp_env):
    # fer already has PT-2026-012 assignment from seed
    _apply("unassign", {"person_id": "fer", "project_code": "PT-2026-012"})
    with db.transaction() as conn:
        active = conn.execute(
            "SELECT COUNT(*) n FROM assignment WHERE person_id='fer' AND project_code='PT-2026-012' AND archived=0"
        ).fetchone()["n"]
        archived = conn.execute(
            "SELECT COUNT(*) n FROM assignment WHERE person_id='fer' AND project_code='PT-2026-012' AND archived=1"
        ).fetchone()["n"]
    assert active == 0
    assert archived == 1


# ---------- availability ----------
def test_handler_availability(tmp_env):
    _apply("availability", {
        "person_id": "santi", "availability_kind": "training",
        "start": "2026-07-01", "end": "2026-07-05", "pct": 50, "reason": "BlackHat",
    })
    with db.transaction() as conn:
        r = conn.execute(
            "SELECT * FROM availability WHERE person_id='santi' AND kind='training' AND start='2026-07-01'"
        ).fetchone()
    assert r["reason"] == "BlackHat"


# ---------- skill_update ----------
def test_handler_skill_update_new(tmp_env):
    _apply("skill_update", {
        "person_id": "tbd_04", "skill_id": "phishing", "level": 2, "growth_interest": True,
    })
    people = yaml_io.load(settings.data_dir / "people.yaml")
    tbd_04 = next(p for p in people if p["id"] == "tbd_04")
    phish = next(s for s in tbd_04["skills"] if s["skill_id"] == "phishing")
    assert phish["level"] == 2
    assert phish["growth_interest"] is True


def test_handler_skill_update_existing(tmp_env):
    _apply("skill_update", {"person_id": "fer", "skill_id": "hacking_cloud", "level": 3})
    people = yaml_io.load(settings.data_dir / "people.yaml")
    fer = next(p for p in people if p["id"] == "fer")
    cloud = next(s for s in fer["skills"] if s["skill_id"] == "hacking_cloud")
    assert cloud["level"] == 3


# ---------- person CRUD ----------
def test_handler_person_create(tmp_env):
    _apply("person_create", {
        "id": "new_hire", "full_name": "New Hire", "office": "madrid",
        "global_level": "junior", "contractual_fte": 0.8, "start_date": "2026-05-01",
    })
    with db.transaction() as conn:
        r = conn.execute("SELECT * FROM person WHERE id='new_hire'").fetchone()
    assert r is not None
    assert r["global_level"] == "junior"


def test_handler_person_update(tmp_env):
    _apply("person_update", {"id": "tbd_01", "global_level": "senior", "contractual_fte": 0.9})
    with db.transaction() as conn:
        r = conn.execute("SELECT * FROM person WHERE id='tbd_01'").fetchone()
    assert r["global_level"] == "senior"
    assert abs(r["contractual_fte"] - 0.9) < 1e-6


def test_handler_person_archive(tmp_env):
    _apply("person_archive", {"id": "tbd_04", "archived": True})
    with db.transaction() as conn:
        r = conn.execute("SELECT archived FROM person WHERE id='tbd_04'").fetchone()
    assert r["archived"] == 1


# ---------- project CRUD ----------
def test_handler_project_create(tmp_env):
    _apply("project_create", {
        "code": "PT-2026-999", "client_alias": "alfa", "type": "pentest_web",
        "window_start": "2026-07-01", "window_end": "2026-07-31",
        "estimated_hours": 160, "status": "pipeline",
        "required_skills": [{"skill_id": "hacking_web", "weight": 3, "min_level": 3}],
    })
    with db.transaction() as conn:
        r = conn.execute("SELECT * FROM project WHERE code='PT-2026-999'").fetchone()
        rs = conn.execute(
            "SELECT * FROM project_required_skill WHERE project_code='PT-2026-999'"
        ).fetchall()
    assert r is not None
    assert r["status"] == "pipeline"
    assert len(rs) == 1


def test_handler_project_update(tmp_env):
    _apply("project_update", {"code": "PT-2026-018", "status": "active", "estimated_hours": 300})
    with db.transaction() as conn:
        r = conn.execute("SELECT * FROM project WHERE code='PT-2026-018'").fetchone()
    assert r["status"] == "active"
    assert r["estimated_hours"] == 300


def test_handler_project_archive(tmp_env):
    _apply("project_archive", {"code": "PT-2026-012", "archived": True})
    with db.transaction() as conn:
        r = conn.execute("SELECT archived FROM project WHERE code='PT-2026-012'").fetchone()
    assert r["archived"] == 1


# ---------- client CRUD ----------
def test_handler_client_create(tmp_env):
    _apply("client_create", {
        "id": "new_bank", "name": "New Bank", "sector": "Banca",
        "size": "Enterprise", "country": "ES", "description": "Prospect",
    })
    with db.transaction() as conn:
        r = conn.execute("SELECT * FROM client WHERE id='new_bank'").fetchone()
    assert r is not None
    assert r["name"] == "New Bank"


def test_handler_client_update(tmp_env):
    _apply("client_update", {"id": "alfa", "description": "Updated desc", "size": "Mid-market"})
    with db.transaction() as conn:
        r = conn.execute("SELECT description, size FROM client WHERE id='alfa'").fetchone()
    assert r["description"] == "Updated desc"
    assert r["size"] == "Mid-market"


def test_handler_client_archive(tmp_env):
    _apply("client_archive", {"id": "interno", "archived": True})
    with db.transaction() as conn:
        r = conn.execute("SELECT archived FROM client WHERE id='interno'").fetchone()
    assert r["archived"] == 1


# ---------- contact CRUD ----------
def test_handler_contact_add(tmp_env):
    _apply("contact_add", {
        "client_id": "gamma", "name": "Ana López", "role": "CTO", "email": "ana@gamma.com",
    })
    with db.transaction() as conn:
        rows = conn.execute("SELECT * FROM contact WHERE client_id='gamma'").fetchall()
    assert any(r["name"] == "Ana López" for r in rows)


def test_handler_contact_update(tmp_env):
    # Alfa starts with 2 contacts — update idx 0
    _apply("contact_update", {
        "client_id": "alfa", "contact_index": 0, "role": "Deputy CISO",
    })
    with db.transaction() as conn:
        r = conn.execute("SELECT role FROM contact WHERE client_id='alfa' AND idx=0").fetchone()
    assert r["role"] == "Deputy CISO"


def test_handler_contact_remove(tmp_env):
    _apply("contact_remove", {"client_id": "alfa", "contact_index": 1})
    with db.transaction() as conn:
        rows = conn.execute("SELECT * FROM contact WHERE client_id='alfa'").fetchall()
    assert len(rows) == 1


# ---------- office CRUD ----------
def test_handler_office_create(tmp_env):
    _apply("office_create", {
        "office_id": "valencia", "city": "Valencia", "country": "ES",
        "lat": 39.4699, "lon": -0.3763,
    })
    with db.transaction() as conn:
        r = conn.execute("SELECT * FROM office WHERE office_id='valencia'").fetchone()
    assert r is not None
    assert r["city"] == "Valencia"


def test_handler_office_update(tmp_env):
    _apply("office_update", {"office_id": "madrid", "lat": 40.5})
    with db.transaction() as conn:
        r = conn.execute("SELECT lat FROM office WHERE office_id='madrid'").fetchone()
    assert abs(r["lat"] - 40.5) < 1e-6


def test_handler_office_archive(tmp_env):
    _apply("office_archive", {"office_id": "remote", "archived": True})
    with db.transaction() as conn:
        r = conn.execute("SELECT archived FROM office WHERE office_id='remote'").fetchone()
    assert r["archived"] == 1


# ---------- skill_label_update ----------
def test_handler_skill_label_update(tmp_env):
    _apply("skill_label_update", {
        "skill_id": "osint",
        "description": "Búsqueda y correlación de información pública.",
    })
    with db.transaction() as conn:
        r = conn.execute("SELECT description FROM skill WHERE id='osint'").fetchone()
    assert r["description"].startswith("Búsqueda")


# ---------- skill_catalog_create / archive ----------
def test_handler_skill_catalog_create(tmp_env):
    _apply("skill_catalog_create", {
        "id": "hacking_kubernetes", "label_es": "Hacking Kubernetes",
        "description": "Explotación de clusters k8s.",
    })
    with db.transaction() as conn:
        r = conn.execute("SELECT * FROM skill WHERE id='hacking_kubernetes'").fetchone()
    assert r is not None
    assert r["label_es"] == "Hacking Kubernetes"
    assert r["archived"] == 0


def test_handler_skill_catalog_archive(tmp_env):
    _apply("skill_catalog_archive", {"id": "acceso_fisico", "archived": True})
    with db.transaction() as conn:
        r = conn.execute("SELECT archived FROM skill WHERE id='acceso_fisico'").fetchone()
    assert r["archived"] == 1


def test_handler_skill_catalog_create_duplicate_raises(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    entry = journal_mod.create_entry("skill_catalog_create", {
        "id": "osint", "label_es": "OSINT v2",
    }, proposer="human")
    with pytest.raises(journal_mod.JournalError):
        journal_mod.apply_entry(entry["id"], applied_by="test")
