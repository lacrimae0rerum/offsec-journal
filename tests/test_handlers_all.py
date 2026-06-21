"""One test per journal handler (20 kinds). Covers the full discriminated union.

Each test: create pending entry → apply → verify the right YAML/row changed.
Avoids the TestClient layer — exercises api.core.journal directly for speed.
"""
from __future__ import annotations

from api.core import db, journal, yaml_io
from api.config import settings


def _apply(kind, payload, team="offsec"):
    entry = journal.create_entry(kind, payload, team, proposer="human")
    journal.apply_entry(entry["id"], team, applied_by="test")
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
    people = yaml_io.load(settings.data_dir / "offsec" / "people.yaml")
    tbd_04 = next(p for p in people if p["id"] == "tbd_04")
    phish = next(s for s in tbd_04["skills"] if s["skill_id"] == "phishing")
    assert phish["level"] == 2
    assert phish["growth_interest"] is True


def test_handler_skill_update_existing(tmp_env):
    _apply("skill_update", {"person_id": "fer", "skill_id": "hacking_cloud", "level": 3})
    people = yaml_io.load(settings.data_dir / "offsec" / "people.yaml")
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
    # A duplicate skill id is now rejected at create-time (no inapplicable pending).
    with pytest.raises(journal_mod.JournalError, match="already exists"):
        journal_mod.create_entry("skill_catalog_create", {
            "id": "osint", "label_es": "OSINT v2",
        }, "offsec", proposer="human")


# ---------- skill_id catalog validation at create time (BUG-APP-001) ----------
def test_skill_update_unknown_skill_rejected_at_create(tmp_env):
    """skill_update referencing a non-existent catalog skill must fail at create
    with a readable error, not at apply with a FOREIGN KEY error."""
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError, match="not found in catalog"):
        journal_mod.create_entry(
            "skill_update",
            {"person_id": "fer", "skill_id": "skill_que_no_existe", "level": 3},
            "offsec", proposer="human",
        )


def test_skill_update_known_skill_still_ok(tmp_env):
    """Regression: a valid skill_id is accepted and applied normally."""
    _apply("skill_update", {"person_id": "fer", "skill_id": "hacking_web", "level": 5})
    with db.transaction() as conn:
        r = conn.execute(
            "SELECT level FROM person_skill WHERE person_id='fer' AND skill_id='hacking_web'"
        ).fetchone()
    assert r["level"] == 5


def test_project_create_unknown_required_skill_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError, match="required skill 'no_such_skill' not found"):
        journal_mod.create_entry(
            "project_create",
            {
                "code": "TST-2026-999", "client_alias": "acme", "type": "pentest_web",
                "window_start": "2026-07-01", "window_end": "2026-07-31",
                "required_skills": [{"skill_id": "no_such_skill", "weight": 1, "min_level": 2}],
            },
            "offsec", proposer="human",
        )


def test_skill_label_update_unknown_skill_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError, match="not found in catalog"):
        journal_mod.create_entry(
            "skill_label_update",
            {"skill_id": "ghost_skill", "label_es": "Fantasma"},
            "offsec", proposer="human",
        )


# ---------- inverted date ranges rejected at create (BUG-APP-002) ----------
def test_assign_inverted_dates_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError, match="on or after"):
        journal_mod.create_entry("assign", {
            "person_id": "fer", "project_code": "PT-2026-012",
            "dedication_pct": 10, "start": "2026-05-01", "end": "2026-04-01",
        }, "offsec", proposer="human")


def test_availability_inverted_dates_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError, match="on or after"):
        journal_mod.create_entry("availability", {
            "person_id": "fer", "availability_kind": "pto",
            "start": "2026-05-10", "end": "2026-05-01",
        }, "offsec", proposer="human")


def test_project_inverted_window_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError, match="on or after"):
        journal_mod.create_entry("project_create", {
            "code": "INV-2026-001", "client_alias": "alfa", "type": "pentest_web",
            "window_start": "2026-06-01", "window_end": "2026-05-01",
        }, "offsec", proposer="human")


# ---------- early validation of state-dependent cases ----------
def test_unassign_without_active_rejected_at_create(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    # santi exists but has no active assignment on PT-2026-012
    with pytest.raises(journal_mod.JournalError, match="no active assignment"):
        journal_mod.create_entry("unassign", {
            "person_id": "santi", "project_code": "PT-2026-012",
        }, "offsec", proposer="human")


def test_duplicate_person_create_rejected_at_create(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError, match="already exists"):
        journal_mod.create_entry("person_create", {
            "id": "fer", "full_name": "Dup", "office": "madrid", "start_date": "2026-01-01",
        }, "offsec", proposer="human")


# ---------- id/code format + non-empty + email validation (BUG-APP-003/004) ----------
def test_person_create_malformed_id_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    for bad in ("Bad Id!", "123abc", "UPPER"):
        with pytest.raises(journal_mod.JournalError):
            journal_mod.create_entry("person_create", {
                "id": bad, "full_name": "X", "office": "madrid", "start_date": "2026-01-01",
            }, "offsec", proposer="human")


def test_project_create_malformed_code_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    for bad in ("bad-code", "ACM-26-1", "acm-2026-001"):
        with pytest.raises(journal_mod.JournalError):
            journal_mod.create_entry("project_create", {
                "code": bad, "client_alias": "alfa", "type": "pentest_web",
                "window_start": "2026-07-01", "window_end": "2026-07-31",
            }, "offsec", proposer="human")


def test_skill_catalog_create_malformed_id_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError):
        journal_mod.create_entry("skill_catalog_create", {
            "id": "Not Snake", "label_es": "X",
        }, "offsec", proposer="human")


def test_empty_required_text_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError):
        journal_mod.create_entry("person_create", {
            "id": "blank_name", "full_name": "   ", "office": "madrid", "start_date": "2026-01-01",
        }, "offsec", proposer="human")
    with pytest.raises(journal_mod.JournalError):
        journal_mod.create_entry("client_create", {"id": "blank_cli", "name": ""},
                                 "offsec", proposer="human")


def test_contact_invalid_email_rejected(tmp_env):
    import pytest
    from api.core import journal as journal_mod
    with pytest.raises(journal_mod.JournalError):
        journal_mod.create_entry("contact_add", {
            "client_id": "alfa", "name": "X", "email": "not-an-email",
        }, "offsec", proposer="human")


# ---------- over-allocation coherence rule (BUG-APP-005) ----------
def test_overallocation_warning():
    from api.core import coherence
    people = [{"id": "p1", "global_level": "senior", "archived": False}]
    assignments = {"p1": [
        {"person_id": "p1", "project_code": "A", "dedication_pct": 70,
         "start": "2026-07-01", "end": "2026-09-30", "archived": False},
        {"person_id": "p1", "project_code": "B", "dedication_pct": 60,
         "start": "2026-08-01", "end": "2026-10-31", "archived": False},
    ]}
    warns = coherence.check_overallocation(people, assignments)
    assert any(w["rule"] == "over_allocation" for w in warns)


def test_no_overallocation_when_sequential():
    from api.core import coherence
    people = [{"id": "p1", "global_level": "senior", "archived": False}]
    assignments = {"p1": [
        {"person_id": "p1", "project_code": "A", "dedication_pct": 100,
         "start": "2026-07-01", "end": "2026-07-31", "archived": False},
        {"person_id": "p1", "project_code": "B", "dedication_pct": 100,
         "start": "2026-08-01", "end": "2026-08-31", "archived": False},
    ]}
    assert coherence.check_overallocation(people, assignments) == []
