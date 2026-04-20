"""Journal apply: assign creates row + updates last_used_on_project.

Also verifies reject requires a reason and archive path is soft-delete.
"""
import pytest

from api.core import db, journal, yaml_io
from api.config import settings


def _create_pending_assign(person_id: str, project_code: str, pct: int = 50) -> str:
    entry = journal.create_entry(
        "assign",
        {
            "person_id": person_id,
            "project_code": project_code,
            "dedication_pct": pct,
            "start": "2026-06-01",
            "end": "2026-06-30",
            "role": "executor",
        },
        proposer="human",
    )
    return entry["id"]


def test_assign_apply_creates_row(tmp_env):
    # fer is not yet on PT-2026-018 (pipeline project)
    entry_id = _create_pending_assign("fer", "PT-2026-018", 40)
    journal.apply_entry(entry_id, applied_by="test")
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT * FROM assignment WHERE person_id='fer' AND project_code='PT-2026-018' AND archived=0"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["dedication_pct"] == 40
    assert rows[0]["role"] == "executor"


def test_assign_updates_last_used_on_project(tmp_env):
    """PT-2026-018 requires hacking_web; fer has it at level 3.
    After apply, fer.skills[hacking_web].last_used_on_project should be PT-2026-018."""
    entry_id = _create_pending_assign("fer", "PT-2026-018", 50)
    journal.apply_entry(entry_id, applied_by="test")
    people = yaml_io.load(settings.data_dir / "people.yaml")
    fer = next(p for p in people if p["id"] == "fer")
    hw = next(s for s in fer["skills"] if s["skill_id"] == "hacking_web")
    assert hw["last_used_on_project"] == "PT-2026-018"


def test_apply_twice_raises(tmp_env):
    entry_id = _create_pending_assign("tbd_04", "PT-2026-018", 20)
    journal.apply_entry(entry_id, applied_by="test")
    with pytest.raises(journal.JournalError):
        journal.apply_entry(entry_id, applied_by="test")


def test_reject_requires_reason(tmp_env):
    entry_id = _create_pending_assign("tbd_04", "PT-2026-018", 20)
    with pytest.raises(journal.JournalError):
        journal.reject_entry(entry_id, "", applied_by="test")
    journal.reject_entry(entry_id, "scope unclear", applied_by="test")
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT status, rejected_reason FROM journal_entry WHERE id = ?", (entry_id,)
        ).fetchone()
    assert row["status"] == "rejected"
    assert row["rejected_reason"] == "scope unclear"


def test_person_archive_is_soft_delete(tmp_env):
    entry = journal.create_entry("person_archive", {"id": "tbd_04", "archived": True}, proposer="human")
    journal.apply_entry(entry["id"], applied_by="test")
    with db.transaction() as conn:
        row = conn.execute("SELECT archived FROM person WHERE id='tbd_04'").fetchone()
    assert row["archived"] == 1
