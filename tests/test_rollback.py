"""Rollback / error-path tests for journal apply.

The contract: if any step of a handler raises, ALL touched YAML files must be
restored from their .bak siblings. Nothing half-applied is tolerated.
"""
import pytest

from api.core import journal, yaml_io
from api.config import settings


def test_apply_invalid_payload_raises_before_mutation(tmp_env):
    """Pydantic validation at POST time (create_entry) stops bad payloads reaching apply."""
    with pytest.raises(Exception):
        journal.create_entry("assign", {"person_id": "fer"}, "offsec", proposer="human")


def test_duplicate_assign_rejected_at_create(tmp_env):
    """fer already has an active PT-2026-012 assignment for that exact start; an exact
    duplicate (same person/project/start) is now rejected at create-time, so no pending
    entry is left and nothing is mutated."""
    original_people = yaml_io.load(settings.data_dir / "offsec" / "people.yaml")
    with pytest.raises(journal.JournalError, match="already exists"):
        journal.create_entry("assign", {
            "person_id": "fer", "project_code": "PT-2026-012",
            "dedication_pct": 50, "start": "2026-04-07", "end": "2026-04-25", "role": "lead",
        }, "offsec", proposer="human")
    # people.yaml untouched (no mid-mutation, no rollback needed)
    after_people = yaml_io.load(settings.data_dir / "offsec" / "people.yaml")
    assert len(original_people) == len(after_people)


def test_create_missing_person_rejected_at_create(tmp_env):
    """Cross-entity refs are now checked at create-time so the journal never
    holds pending entries pointing at non-existent persons. No mutation, no
    rollback needed."""
    original = yaml_io.load(settings.data_dir / "offsec" / "people.yaml")
    with pytest.raises(journal.JournalError, match="nonexistent_user"):
        journal.create_entry("skill_update", {
            "person_id": "nonexistent_user", "skill_id": "osint", "level": 3,
        }, "offsec", proposer="human")
    after = yaml_io.load(settings.data_dir / "offsec" / "people.yaml")
    assert original == after


def test_create_missing_project_rejected_at_create(tmp_env):
    original = yaml_io.load(settings.data_dir / "offsec" / "projects.yaml")
    with pytest.raises(journal.JournalError, match="NON-EXIST-001"):
        journal.create_entry("project_archive", {"code": "NON-EXIST-001"}, "offsec", proposer="human")
    after = yaml_io.load(settings.data_dir / "offsec" / "projects.yaml")
    assert original == after


def test_backup_file_exists_after_apply(tmp_env):
    """After a successful apply, the .bak should sit next to the mutated file."""
    entry = journal.create_entry("availability", {
        "person_id": "tbd_01", "availability_kind": "pto",
        "start": "2026-08-01", "end": "2026-08-05", "pct": 100, "reason": "holiday",
    }, "offsec", proposer="human")
    journal.apply_entry(entry["id"], "offsec", applied_by="test")
    bak = settings.data_dir / "offsec" / "availability.yaml.bak"
    assert bak.exists()


def test_reject_of_already_applied_raises(tmp_env):
    entry = journal.create_entry("availability", {
        "person_id": "tbd_01", "availability_kind": "training",
        "start": "2026-09-01", "end": "2026-09-05", "pct": 50, "reason": "conf",
    }, "offsec", proposer="human")
    journal.apply_entry(entry["id"], "offsec", applied_by="test")
    with pytest.raises(journal.JournalError):
        journal.reject_entry(entry["id"], "offsec", "cambio de idea", applied_by="test")


def test_contact_remove_out_of_range_rejected_at_create(tmp_env):
    """An out-of-range contact_index is now rejected at create-time."""
    original = yaml_io.load(settings.data_dir / "offsec" / "clients.yaml")
    with pytest.raises(journal.JournalError, match="out of range"):
        journal.create_entry("contact_remove", {
            "client_id": "alfa", "contact_index": 99,
        }, "offsec", proposer="human")
    after = yaml_io.load(settings.data_dir / "offsec" / "clients.yaml")
    assert original == after
