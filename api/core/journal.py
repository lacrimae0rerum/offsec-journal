"""Apply / reject journal entries with .bak rollback.

apply(entry_id) dispatches on kind to a handler that:
  1. Creates .bak of the target YAML file(s)
  2. Mutates the YAML document with ruamel (preserving comments/order)
  3. Writes back, then calls sync() to rebuild the SQLite cache
  4. If anything raises, restore(.bak) all touched files and re-raise
  5. On success, mutate journal.yaml to mark the entry applied+timestamp

All timestamps are UTC ISO-8601 strings. Proposer is already set when the
entry was created (llm via /api/chat tool-call, human via POST /api/journal).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from api.config import settings
from api.core import yaml_io
from api.core.sync import sync


class JournalError(Exception):
    """Wraps anything that goes wrong during apply, after rollback."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_journal() -> list[dict]:
    return yaml_io.load(settings.data_dir / "journal.yaml") or []


def _find_entry(entries: list[dict], entry_id: str) -> dict | None:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    return None


def _write_journal(entries: list[dict]) -> None:
    yaml_io.dump(settings.data_dir / "journal.yaml", entries)


def apply_entry(entry_id: str, *, applied_by: str = "unknown") -> dict:
    data_dir = settings.data_dir
    journal_path = data_dir / "journal.yaml"

    entries = _load_journal()
    entry = _find_entry(entries, entry_id)
    if entry is None:
        raise JournalError(f"entry {entry_id} not found")
    if entry.get("status") != "pending":
        raise JournalError(f"entry {entry_id} is {entry.get('status')}, not pending")

    kind = entry["kind"]
    handler = HANDLERS.get(kind)
    if handler is None:
        raise JournalError(f"no handler for kind={kind}")

    touched: list[Path] = []
    try:
        payload = dict(entry.get("payload") or {})
        touched = handler(payload, data_dir)
        # On successful mutation, also update journal.yaml itself
        yaml_io.backup(journal_path)
        touched.append(journal_path)
        entry["status"] = "applied"
        entry["applied_at"] = _utc_now_iso()
        entry["applied_by"] = applied_by
        _write_journal(entries)
        # Propagate to SQLite
        sync()
    except Exception as e:
        for p in touched:
            try:
                yaml_io.restore(p)
            except Exception:
                pass
        raise JournalError(f"apply failed: {e}") from e

    return entry


def reject_entry(entry_id: str, reason: str, *, applied_by: str = "unknown") -> dict:
    entries = _load_journal()
    entry = _find_entry(entries, entry_id)
    if entry is None:
        raise JournalError(f"entry {entry_id} not found")
    if entry.get("status") != "pending":
        raise JournalError(f"entry is {entry.get('status')}, not pending")
    if not reason or not reason.strip():
        raise JournalError("reject requires a reason")
    entry["status"] = "rejected"
    entry["rejected_reason"] = reason.strip()
    entry["applied_by"] = applied_by
    yaml_io.backup(settings.data_dir / "journal.yaml")
    _write_journal(entries)
    sync()
    return entry


# =============================================================================
# Handlers — return list of Paths that were backed up + mutated.
# =============================================================================
Handler = Callable[[dict, Path], list[Path]]


def _auto_touch_last_used(data_dir: Path, person_id: str, project_code: str) -> None:
    """When an assign is applied, update last_used_on_project for each skill
    the person has with level≥1 that the project requires."""
    people_path = data_dir / "people.yaml"
    projects_path = data_dir / "projects.yaml"
    people = yaml_io.load(people_path) or []
    projects = yaml_io.load(projects_path) or []
    project = next((p for p in projects if p.get("code") == project_code), None)
    if project is None:
        return
    req_ids = {rs["skill_id"] for rs in (project.get("required_skills") or [])}
    changed = False
    for p in people:
        if p.get("id") != person_id:
            continue
        for ps in p.get("skills") or []:
            if ps.get("skill_id") in req_ids and int(ps.get("level", 0)) >= 1:
                ps["last_used_on_project"] = project_code
                changed = True
    if changed:
        yaml_io.dump(people_path, people)


def _h_assign(payload: dict, data_dir: Path) -> list[Path]:
    assignments_path = data_dir / "assignments.yaml"
    yaml_io.backup(assignments_path)
    rows = yaml_io.load(assignments_path) or []
    # Reject archived entries match too — we want one active row per (person, project, start)
    exists = any(
        r for r in rows
        if r.get("person_id") == payload["person_id"]
        and r.get("project_code") == payload["project_code"]
        and str(r.get("start")) == str(payload["start"])
    )
    if exists:
        raise JournalError("assignment already exists; create unassign + new assign to replace")
    rows.append({
        "person_id": payload["person_id"],
        "project_code": payload["project_code"],
        "dedication_pct": int(payload["dedication_pct"]),
        "start": payload["start"],
        "end": payload["end"],
        "role": payload.get("role", "executor"),
        "archived": False,
    })
    yaml_io.dump(assignments_path, rows)
    # Side-effect: update last_used_on_project
    yaml_io.backup(data_dir / "people.yaml")
    _auto_touch_last_used(data_dir, payload["person_id"], payload["project_code"])
    return [assignments_path, data_dir / "people.yaml"]


def _h_unassign(payload: dict, data_dir: Path) -> list[Path]:
    assignments_path = data_dir / "assignments.yaml"
    yaml_io.backup(assignments_path)
    rows = yaml_io.load(assignments_path) or []
    found = False
    for r in rows:
        if (r.get("person_id") == payload["person_id"]
            and r.get("project_code") == payload["project_code"]
            and not r.get("archived")):
            r["archived"] = True
            found = True
    if not found:
        raise JournalError("no active assignment matches")
    yaml_io.dump(assignments_path, rows)
    return [assignments_path]


def _h_availability(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "availability.yaml"
    yaml_io.backup(path)
    rows = yaml_io.load(path) or []
    rows.append({
        "person_id": payload["person_id"],
        "kind": payload["availability_kind"],
        "start": payload["start"],
        "end": payload["end"],
        "pct": int(payload.get("pct", 100)),
        "reason": payload.get("reason", ""),
        "archived": False,
    })
    yaml_io.dump(path, rows)
    return [path]


def _h_skill_update(payload: dict, data_dir: Path) -> list[Path]:
    people_path = data_dir / "people.yaml"
    yaml_io.backup(people_path)
    people = yaml_io.load(people_path) or []
    target = next((p for p in people if p.get("id") == payload["person_id"]), None)
    if target is None:
        raise JournalError(f"person {payload['person_id']} not found")
    skills = target.setdefault("skills", [])
    existing = next((s for s in skills if s.get("skill_id") == payload["skill_id"]), None)
    if existing:
        existing["level"] = int(payload["level"])
        if payload.get("growth_interest") is not None:
            existing["growth_interest"] = bool(payload["growth_interest"])
    else:
        skills.append({
            "skill_id": payload["skill_id"],
            "level": int(payload["level"]),
            "last_used_on_project": None,
            "growth_interest": bool(payload.get("growth_interest") or False),
        })
    yaml_io.dump(people_path, people)
    return [people_path]


def _h_person_create(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "people.yaml"
    yaml_io.backup(path)
    people = yaml_io.load(path) or []
    if any(p.get("id") == payload["id"] for p in people):
        raise JournalError(f"person id '{payload['id']}' already exists")
    people.append({
        "id": payload["id"],
        "full_name": payload["full_name"],
        "office": payload["office"],
        "city": payload.get("city", ""),
        "timezone": payload.get("timezone", "CET"),
        "languages": payload.get("languages", []),
        "base_role": payload.get("base_role", "pentester"),
        "global_level": payload.get("global_level", "junior"),
        "contractual_fte": float(payload.get("contractual_fte", 1.0)),
        "start_date": payload["start_date"],
        "archived": False,
        "skills": [],
    })
    yaml_io.dump(path, people)
    return [path]


def _h_person_update(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "people.yaml"
    yaml_io.backup(path)
    people = yaml_io.load(path) or []
    target = next((p for p in people if p.get("id") == payload["id"]), None)
    if target is None:
        raise JournalError(f"person '{payload['id']}' not found")
    for key in ("full_name", "office", "city", "timezone", "languages",
                "base_role", "global_level", "contractual_fte"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, people)
    return [path]


def _h_person_archive(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "people.yaml"
    yaml_io.backup(path)
    people = yaml_io.load(path) or []
    target = next((p for p in people if p.get("id") == payload["id"]), None)
    if target is None:
        raise JournalError(f"person '{payload['id']}' not found")
    target["archived"] = bool(payload.get("archived", True))
    yaml_io.dump(path, people)
    return [path]


def _h_project_create(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "projects.yaml"
    yaml_io.backup(path)
    projects = yaml_io.load(path) or []
    if any(p.get("code") == payload["code"] for p in projects):
        raise JournalError(f"project '{payload['code']}' already exists")
    projects.append({
        "code": payload["code"],
        "client_alias": payload["client_alias"],
        "type": payload["type"],
        "window_start": payload["window_start"],
        "window_end": payload["window_end"],
        "estimated_hours": int(payload.get("estimated_hours", 0)),
        "status": payload.get("status", "pipeline"),
        "archived": False,
        "required_skills": payload.get("required_skills", []),
    })
    yaml_io.dump(path, projects)
    return [path]


def _h_project_update(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "projects.yaml"
    yaml_io.backup(path)
    projects = yaml_io.load(path) or []
    target = next((p for p in projects if p.get("code") == payload["code"]), None)
    if target is None:
        raise JournalError(f"project '{payload['code']}' not found")
    for key in ("client_alias", "type", "window_start", "window_end",
                "estimated_hours", "status", "required_skills"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, projects)
    return [path]


def _h_project_archive(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "projects.yaml"
    yaml_io.backup(path)
    projects = yaml_io.load(path) or []
    target = next((p for p in projects if p.get("code") == payload["code"]), None)
    if target is None:
        raise JournalError(f"project '{payload['code']}' not found")
    target["archived"] = bool(payload.get("archived", True))
    yaml_io.dump(path, projects)
    return [path]


def _h_client_create(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "clients.yaml"
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    if any(c.get("id") == payload["id"] for c in clients):
        raise JournalError(f"client '{payload['id']}' already exists")
    clients.append({
        "id": payload["id"],
        "name": payload["name"],
        "sector": payload.get("sector", ""),
        "size": payload.get("size", ""),
        "country": payload.get("country", ""),
        "status": "activo",
        "archived": False,
        "description": payload.get("description", ""),
        "contacts": [],
    })
    yaml_io.dump(path, clients)
    return [path]


def _h_client_update(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "clients.yaml"
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['id']}' not found")
    for key in ("name", "sector", "size", "country", "description"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, clients)
    return [path]


def _h_client_archive(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "clients.yaml"
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['id']}' not found")
    target["archived"] = bool(payload.get("archived", True))
    yaml_io.dump(path, clients)
    return [path]


def _h_contact_add(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "clients.yaml"
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["client_id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['client_id']}' not found")
    contacts = target.setdefault("contacts", [])
    contacts.append({
        "name": payload["name"],
        "role": payload.get("role", ""),
        "email": payload.get("email", ""),
        "phone": payload.get("phone", ""),
    })
    yaml_io.dump(path, clients)
    return [path]


def _h_contact_update(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "clients.yaml"
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["client_id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['client_id']}' not found")
    contacts = target.get("contacts") or []
    idx = int(payload["contact_index"])
    if not (0 <= idx < len(contacts)):
        raise JournalError(f"contact_index {idx} out of range")
    for key in ("name", "role", "email", "phone"):
        if payload.get(key) is not None:
            contacts[idx][key] = payload[key]
    yaml_io.dump(path, clients)
    return [path]


def _h_contact_remove(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "clients.yaml"
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["client_id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['client_id']}' not found")
    contacts = target.get("contacts") or []
    idx = int(payload["contact_index"])
    if not (0 <= idx < len(contacts)):
        raise JournalError(f"contact_index {idx} out of range")
    contacts.pop(idx)
    yaml_io.dump(path, clients)
    return [path]


def _h_office_create(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "offices.yaml"
    yaml_io.backup(path)
    offices = yaml_io.load(path) or []
    if any(o.get("office_id") == payload["office_id"] for o in offices):
        raise JournalError(f"office '{payload['office_id']}' already exists")
    offices.append({
        "office_id": payload["office_id"],
        "city": payload["city"],
        "country": payload.get("country", ""),
        "lat": float(payload.get("lat", 0)),
        "lon": float(payload.get("lon", 0)),
        "archived": False,
    })
    yaml_io.dump(path, offices)
    return [path]


def _h_office_update(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "offices.yaml"
    yaml_io.backup(path)
    offices = yaml_io.load(path) or []
    target = next((o for o in offices if o.get("office_id") == payload["office_id"]), None)
    if target is None:
        raise JournalError(f"office '{payload['office_id']}' not found")
    for key in ("city", "country", "lat", "lon"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, offices)
    return [path]


def _h_office_archive(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "offices.yaml"
    yaml_io.backup(path)
    offices = yaml_io.load(path) or []
    target = next((o for o in offices if o.get("office_id") == payload["office_id"]), None)
    if target is None:
        raise JournalError(f"office '{payload['office_id']}' not found")
    target["archived"] = bool(payload.get("archived", True))
    yaml_io.dump(path, offices)
    return [path]


def _h_skill_label_update(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "skills.yaml"
    yaml_io.backup(path)
    skills = yaml_io.load(path) or []
    target = next((s for s in skills if s.get("id") == payload["skill_id"]), None)
    if target is None:
        raise JournalError(f"skill '{payload['skill_id']}' not found")
    if payload.get("label_es") is not None:
        target["label_es"] = payload["label_es"]
    if payload.get("description") is not None:
        target["description"] = payload["description"]
    yaml_io.dump(path, skills)
    return [path]


def _h_skill_catalog_create(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "skills.yaml"
    yaml_io.backup(path)
    skills = yaml_io.load(path) or []
    if any(s.get("id") == payload["id"] for s in skills):
        raise JournalError(f"skill '{payload['id']}' already exists")
    skills.append({
        "id": payload["id"],
        "label_es": payload["label_es"],
        "description": payload.get("description", "TODO: operator-defined"),
        "archived": False,
    })
    yaml_io.dump(path, skills)
    return [path]


def _h_skill_catalog_archive(payload: dict, data_dir: Path) -> list[Path]:
    path = data_dir / "skills.yaml"
    yaml_io.backup(path)
    skills = yaml_io.load(path) or []
    target = next((s for s in skills if s.get("id") == payload["id"]), None)
    if target is None:
        raise JournalError(f"skill '{payload['id']}' not found")
    target["archived"] = bool(payload.get("archived", True))
    yaml_io.dump(path, skills)
    return [path]


HANDLERS: dict[str, Handler] = {
    "assign": _h_assign,
    "unassign": _h_unassign,
    "availability": _h_availability,
    "skill_update": _h_skill_update,
    "person_create": _h_person_create,
    "person_update": _h_person_update,
    "person_archive": _h_person_archive,
    "project_create": _h_project_create,
    "project_update": _h_project_update,
    "project_archive": _h_project_archive,
    "client_create": _h_client_create,
    "client_update": _h_client_update,
    "client_archive": _h_client_archive,
    "contact_add": _h_contact_add,
    "contact_update": _h_contact_update,
    "contact_remove": _h_contact_remove,
    "office_create": _h_office_create,
    "office_update": _h_office_update,
    "office_archive": _h_office_archive,
    "skill_catalog_create": _h_skill_catalog_create,
    "skill_catalog_archive": _h_skill_catalog_archive,
    "skill_label_update": _h_skill_label_update,
}


def create_entry(kind: str, payload: dict, *, proposer: str = "human") -> dict:
    """Create a new pending entry. Validates via JournalPayload discriminator."""
    from api.models.journal import JournalPayload
    from pydantic import TypeAdapter
    import ulid

    adapter = TypeAdapter(JournalPayload)
    validated = adapter.validate_python({"kind": kind, **payload}).model_dump(mode="json")
    validated.pop("kind", None)

    entry = {
        "id": str(ulid.ULID()),
        "timestamp": _utc_now_iso(),
        "proposer": proposer,
        "kind": kind,
        "payload": validated,
        "status": "pending",
        "applied_at": None,
        "applied_by": None,
        "rejected_reason": None,
    }
    journal_path = settings.data_dir / "journal.yaml"
    yaml_io.backup(journal_path)
    entries = yaml_io.load(journal_path) or []
    entries.append(entry)
    yaml_io.dump(journal_path, entries)
    sync()
    return entry
