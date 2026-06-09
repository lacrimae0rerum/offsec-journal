"""Apply / reject journal entries with .bak rollback (multi-team).

Public API takes `team_slug` explicitly. The journal YAML lives under
data/<team_slug>/journal.yaml and mutations target data/<team_slug>/*.yaml.

apply_entry(entry_id, team_slug) dispatches on kind to a handler that:
  1. Creates .bak of the target YAML file(s)
  2. Mutates the YAML document with ruamel (preserving comments/order)
  3. Writes back, then calls sync() to rebuild the SQLite cache
  4. If anything raises, restore(.bak) all touched files and re-raise
  5. On success, marks the entry applied + timestamp in journal.yaml

All timestamps are UTC ISO-8601 strings.

Shared tables (`skills`): the three skill_catalog_* handlers write to
data/skills.yaml regardless of team_slug — they ignore the team argument.
Everything else writes to data/<team_slug>/<entity>.yaml.
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


def validate_payload(kind: str, payload: dict) -> dict:
    """Validate payload shape via the discriminated-union model.

    Returns the sanitized dict (kind stripped, types coerced). Raises
    `JournalError` if the payload is malformed. Safe to call from route
    handlers before any write — the goal is to fail 400 before touching
    data/<team>/journal.yaml.
    """
    from pydantic import TypeAdapter, ValidationError
    from api.models.journal import JournalPayload
    try:
        adapter = TypeAdapter(JournalPayload)
        validated = adapter.validate_python({"kind": kind, **payload}).model_dump(mode="json")
    except ValidationError as e:
        raise JournalError(f"invalid payload for kind='{kind}': {e.errors()[0]['msg']}") from e
    validated.pop("kind", None)
    return validated


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _journal_path(team_slug: str) -> Path:
    return yaml_io.tenant_path(team_slug, "journal", settings.data_dir)


def _load_journal(team_slug: str) -> list[dict]:
    return yaml_io.load(_journal_path(team_slug)) or []


def _find_entry(entries: list[dict], entry_id: str) -> dict | None:
    for e in entries:
        if e.get("id") == entry_id:
            return e
    return None


def _write_journal(entries: list[dict], team_slug: str) -> None:
    yaml_io.dump(_journal_path(team_slug), entries)


def apply_entry(entry_id: str, team_slug: str, *,
                applied_by: str = "unknown") -> dict:
    data_dir = settings.data_dir
    journal_path = _journal_path(team_slug)

    entries = _load_journal(team_slug)
    entry = _find_entry(entries, entry_id)
    if entry is None:
        raise JournalError(f"entry {entry_id} not found in team '{team_slug}'")
    if entry.get("status") != "pending":
        raise JournalError(f"entry {entry_id} is {entry.get('status')}, not pending")

    kind = entry["kind"]
    handler = HANDLERS.get(kind)
    if handler is None:
        raise JournalError(f"no handler for kind={kind}")

    touched: list[Path] = []
    try:
        payload = dict(entry.get("payload") or {})
        touched = handler(payload, team_slug, data_dir)
        yaml_io.backup(journal_path)
        touched.append(journal_path)
        entry["status"] = "applied"
        entry["applied_at"] = _utc_now_iso()
        entry["applied_by"] = applied_by
        _write_journal(entries, team_slug)
        sync()
    except Exception as e:
        # Any failure mid-apply must restore every touched YAML file. The
        # restore itself can fail (disk full, permissions, .bak missing) —
        # log each failure rather than silently swallowing; an inconsistent
        # filesystem state is a big deal and the operator needs to know.
        from loguru import logger
        for p in touched:
            try:
                yaml_io.restore(p)
            except (FileNotFoundError, OSError) as restore_err:
                logger.error(
                    "apply rollback: failed to restore {} after {}: {}",
                    p, type(e).__name__, restore_err,
                )
        raise JournalError(f"apply failed: {e}") from e

    return entry


def reject_entry(entry_id: str, team_slug: str, reason: str, *,
                 applied_by: str = "unknown") -> dict:
    entries = _load_journal(team_slug)
    entry = _find_entry(entries, entry_id)
    if entry is None:
        raise JournalError(f"entry {entry_id} not found in team '{team_slug}'")
    if entry.get("status") != "pending":
        raise JournalError(f"entry is {entry.get('status')}, not pending")
    if not reason or not reason.strip():
        raise JournalError("reject requires a reason")
    entry["status"] = "rejected"
    entry["rejected_reason"] = reason.strip()
    entry["applied_by"] = applied_by
    yaml_io.backup(_journal_path(team_slug))
    _write_journal(entries, team_slug)
    sync()
    return entry


# =============================================================================
# Handlers — (payload, team_slug, data_dir) -> list[Path]
# Return the list of Paths that were backed up + mutated so apply_entry can
# rollback them if sync or the journal write fails.
# =============================================================================
Handler = Callable[[dict, str, Path], list[Path]]


def _tp(team_slug: str, entity: str, data_dir: Path) -> Path:
    return yaml_io.tenant_path(team_slug, entity, data_dir)


def _sp(entity: str, data_dir: Path) -> Path:
    return yaml_io.shared_path(entity, data_dir)


def _auto_touch_last_used(data_dir: Path, team_slug: str,
                          person_id: str, project_code: str) -> None:
    """When an assign applies, update last_used_on_project for each skill
    the person has with level≥1 that the project requires."""
    people_path = _tp(team_slug, "people", data_dir)
    projects_path = _tp(team_slug, "projects", data_dir)
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


def _h_assign(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    """Create an assignment row, or reactivate a previously archived one.

    Active duplicate (same person/project/start, archived=False) is rejected —
    that's a legitimate ambiguity the operator should resolve. Archived
    duplicate gets revived with the new payload's pct/end/role, since
    archive is a soft-delete and the natural unique-key shouldn't block reuse.
    """
    assignments_path = _tp(team_slug, "assignments", data_dir)
    yaml_io.backup(assignments_path)
    rows = yaml_io.load(assignments_path) or []
    same_triple = [
        r for r in rows
        if r.get("person_id") == payload["person_id"]
        and r.get("project_code") == payload["project_code"]
        and str(r.get("start")) == str(payload["start"])
    ]
    active_dup = next((r for r in same_triple if not r.get("archived")), None)
    if active_dup is not None:
        raise JournalError("assignment already exists; create unassign + new assign to replace")
    archived_dup = next((r for r in same_triple if r.get("archived")), None)
    if archived_dup is not None:
        archived_dup["dedication_pct"] = int(payload["dedication_pct"])
        archived_dup["end"] = payload["end"]
        archived_dup["role"] = payload.get("role", "executor")
        archived_dup["archived"] = False
    else:
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
    people_path = _tp(team_slug, "people", data_dir)
    yaml_io.backup(people_path)
    _auto_touch_last_used(data_dir, team_slug, payload["person_id"], payload["project_code"])
    return [assignments_path, people_path]


def _h_unassign(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "assignments", data_dir)
    yaml_io.backup(path)
    rows = yaml_io.load(path) or []
    found = False
    for r in rows:
        if (r.get("person_id") == payload["person_id"]
            and r.get("project_code") == payload["project_code"]
            and not r.get("archived")):
            r["archived"] = True
            found = True
    if not found:
        raise JournalError("no active assignment matches")
    yaml_io.dump(path, rows)
    return [path]


def _h_availability(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "availability", data_dir)
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


def _h_skill_update(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "people", data_dir)
    yaml_io.backup(path)
    people = yaml_io.load(path) or []
    target = next((p for p in people if p.get("id") == payload["person_id"]), None)
    if target is None:
        raise JournalError(f"person {payload['person_id']} not found in team '{team_slug}'")
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
    yaml_io.dump(path, people)
    return [path]


def _h_person_create(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "people", data_dir)
    yaml_io.backup(path)
    people = yaml_io.load(path) or []
    if any(p.get("id") == payload["id"] for p in people):
        raise JournalError(f"person id '{payload['id']}' already exists in team '{team_slug}'")
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


def _h_person_update(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "people", data_dir)
    yaml_io.backup(path)
    people = yaml_io.load(path) or []
    target = next((p for p in people if p.get("id") == payload["id"]), None)
    if target is None:
        raise JournalError(f"person '{payload['id']}' not found in team '{team_slug}'")
    for key in ("full_name", "office", "city", "timezone", "languages",
                "base_role", "global_level", "contractual_fte"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, people)
    return [path]


def _archive_by_field(
    entity_label: str,
    entity_name: str,   # yaml_io entity name, e.g. "people"
    id_field: str,      # field name in payload AND in the yaml row (e.g. "id", "code", "office_id")
    payload: dict,
    team_slug: str,
    data_dir: Path,
    *,
    shared: bool = False,
) -> list[Path]:
    """Generic soft-delete handler used by person/project/client/office/skill_catalog.

    Looks up a row by `payload[id_field]` in the target YAML file, flips
    `archived` to the payload's value (defaults True), and writes back. Raises
    JournalError if the row isn't found.
    """
    path = _sp(entity_name, data_dir) if shared else _tp(team_slug, entity_name, data_dir)
    yaml_io.backup(path)
    rows = yaml_io.load(path) or []
    target = next((r for r in rows if r.get(id_field) == payload[id_field]), None)
    if target is None:
        scope = "" if shared else f" in team '{team_slug}'"
        raise JournalError(f"{entity_label} '{payload[id_field]}' not found{scope}")
    target["archived"] = bool(payload.get("archived", True))
    yaml_io.dump(path, rows)
    return [path]


def _h_person_archive(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    return _archive_by_field("person", "people", "id", payload, team_slug, data_dir)


def _h_project_create(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "projects", data_dir)
    yaml_io.backup(path)
    projects = yaml_io.load(path) or []
    if any(p.get("code") == payload["code"] for p in projects):
        raise JournalError(f"project '{payload['code']}' already exists in team '{team_slug}'")
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


def _h_project_update(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "projects", data_dir)
    yaml_io.backup(path)
    projects = yaml_io.load(path) or []
    target = next((p for p in projects if p.get("code") == payload["code"]), None)
    if target is None:
        raise JournalError(f"project '{payload['code']}' not found in team '{team_slug}'")
    for key in ("client_alias", "type", "window_start", "window_end",
                "estimated_hours", "status", "required_skills"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, projects)
    return [path]


def _h_project_archive(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    return _archive_by_field("project", "projects", "code", payload, team_slug, data_dir)


def _h_client_create(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "clients", data_dir)
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    if any(c.get("id") == payload["id"] for c in clients):
        raise JournalError(f"client '{payload['id']}' already exists in team '{team_slug}'")
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


def _h_client_update(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "clients", data_dir)
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['id']}' not found in team '{team_slug}'")
    for key in ("name", "sector", "size", "country", "description"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, clients)
    return [path]


def _h_client_archive(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    return _archive_by_field("client", "clients", "id", payload, team_slug, data_dir)


def _h_contact_add(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "clients", data_dir)
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["client_id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['client_id']}' not found in team '{team_slug}'")
    contacts = target.setdefault("contacts", [])
    contacts.append({
        "name": payload["name"],
        "role": payload.get("role", ""),
        "email": payload.get("email", ""),
        "phone": payload.get("phone", ""),
    })
    yaml_io.dump(path, clients)
    return [path]


def _h_contact_update(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "clients", data_dir)
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["client_id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['client_id']}' not found in team '{team_slug}'")
    contacts = target.get("contacts") or []
    idx = int(payload["contact_index"])
    if not (0 <= idx < len(contacts)):
        raise JournalError(f"contact_index {idx} out of range")
    for key in ("name", "role", "email", "phone"):
        if payload.get(key) is not None:
            contacts[idx][key] = payload[key]
    yaml_io.dump(path, clients)
    return [path]


def _h_contact_remove(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "clients", data_dir)
    yaml_io.backup(path)
    clients = yaml_io.load(path) or []
    target = next((c for c in clients if c.get("id") == payload["client_id"]), None)
    if target is None:
        raise JournalError(f"client '{payload['client_id']}' not found in team '{team_slug}'")
    contacts = target.get("contacts") or []
    idx = int(payload["contact_index"])
    if not (0 <= idx < len(contacts)):
        raise JournalError(f"contact_index {idx} out of range")
    contacts.pop(idx)
    yaml_io.dump(path, clients)
    return [path]


def _h_office_create(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "offices", data_dir)
    yaml_io.backup(path)
    offices = yaml_io.load(path) or []
    if any(o.get("office_id") == payload["office_id"] for o in offices):
        raise JournalError(f"office '{payload['office_id']}' already exists in team '{team_slug}'")
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


def _h_office_update(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _tp(team_slug, "offices", data_dir)
    yaml_io.backup(path)
    offices = yaml_io.load(path) or []
    target = next((o for o in offices if o.get("office_id") == payload["office_id"]), None)
    if target is None:
        raise JournalError(f"office '{payload['office_id']}' not found in team '{team_slug}'")
    for key in ("city", "country", "lat", "lon"):
        if payload.get(key) is not None:
            target[key] = payload[key]
    yaml_io.dump(path, offices)
    return [path]


def _h_office_archive(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    return _archive_by_field("office", "offices", "office_id", payload, team_slug, data_dir)


# Shared: skill catalog. These mutate data/skills.yaml regardless of team.
def _h_skill_label_update(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _sp("skills", data_dir)
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


def _h_skill_catalog_create(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    path = _sp("skills", data_dir)
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


def _h_skill_catalog_archive(payload: dict, team_slug: str, data_dir: Path) -> list[Path]:
    return _archive_by_field("skill", "skills", "id", payload, team_slug, data_dir, shared=True)


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


def _check_referenced_entities(kind: str, payload: dict, team_slug: str) -> None:
    """Reject entries that point at non-existent or archived entities.

    Without this, the entry sits as `pending` happily and only blows up at
    apply-time with a `FOREIGN KEY constraint failed` from the SQLite sync —
    confusing for users. We catch the most common cross-entity references
    here so the route returns 400 at create time with a readable message.
    """
    data_dir = settings.data_dir

    def _exists(entity: str, id_field: str, value: str, *, allow_archived: bool = False) -> bool:
        rows = yaml_io.load(_tp(team_slug, entity, data_dir)) or []
        return any(
            r.get(id_field) == value and (allow_archived or not r.get("archived"))
            for r in rows
        )

    if kind == "assign":
        if not _exists("people", "id", payload.get("person_id")):
            raise JournalError(f"person '{payload.get('person_id')}' not found in team '{team_slug}'")
        if not _exists("projects", "code", payload.get("project_code")):
            raise JournalError(f"project '{payload.get('project_code')}' not found in team '{team_slug}'")
    elif kind in ("person_update", "person_archive"):
        if not _exists("people", "id", payload.get("id"), allow_archived=True):
            raise JournalError(f"person '{payload.get('id')}' not found in team '{team_slug}'")
    elif kind == "skill_update":
        if not _exists("people", "id", payload.get("person_id"), allow_archived=True):
            raise JournalError(f"person '{payload.get('person_id')}' not found in team '{team_slug}'")
    elif kind in ("project_update", "project_archive"):
        if not _exists("projects", "code", payload.get("code"), allow_archived=True):
            raise JournalError(f"project '{payload.get('code')}' not found in team '{team_slug}'")
    elif kind in ("client_update", "client_archive"):
        if not _exists("clients", "id", payload.get("id"), allow_archived=True):
            raise JournalError(f"client '{payload.get('id')}' not found in team '{team_slug}'")
    elif kind in ("contact_add", "contact_update", "contact_remove"):
        if not _exists("clients", "id", payload.get("client_id"), allow_archived=True):
            raise JournalError(f"client '{payload.get('client_id')}' not found in team '{team_slug}'")
    elif kind == "unassign":
        # unassign references existing assignment rows; person/project must exist
        if not _exists("people", "id", payload.get("person_id"), allow_archived=True):
            raise JournalError(f"person '{payload.get('person_id')}' not found in team '{team_slug}'")
        if not _exists("projects", "code", payload.get("project_code"), allow_archived=True):
            raise JournalError(f"project '{payload.get('project_code')}' not found in team '{team_slug}'")


def create_entry(kind: str, payload: dict, team_slug: str, *,
                 proposer: str = "human",
                 created_by_user_id: str | None = None) -> dict:
    """Create a new pending entry in team's journal.

    Callers are expected to have already validated `payload` via
    `validate_payload(kind, payload)` — we re-run the check here as a safety
    net. If you call this without validating first and the payload is
    malformed, a JournalError is raised before any YAML/DB write happens.
    """
    import ulid

    validated = validate_payload(kind, payload)
    _check_referenced_entities(kind, validated, team_slug)

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
        "created_by_user_id": created_by_user_id,
    }
    journal_path = _journal_path(team_slug)
    yaml_io.backup(journal_path)
    entries = yaml_io.load(journal_path) or []
    entries.append(entry)
    yaml_io.dump(journal_path, entries)
    sync()
    return entry
