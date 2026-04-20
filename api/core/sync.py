"""Rebuild SQLite cache from YAML source-of-truth.

Idempotent: running twice is a no-op. Destructive diffs (entity removed from
YAML but referenced by rows in DB) require `--confirm` to proceed. Normal
`make up` calls `sync` without --confirm; if a destructive diff is detected
it aborts with exit code 2 and prints the diff.

Invoke: `python -m api.core.sync` or `python -m api.core.sync --confirm`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from api.config import settings
from api.core import db, yaml_io


def _json_default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(f"not serializable: {type(o).__name__}")


def _json_dumps(obj) -> str:
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


NOTE_SEP_RE = re.compile(
    r"^---\s+(?P<ts>\S+)\s+\|\s+(?P<author>[^|]+?)\s+\|\s+tags:\s*(?P<tags>.*?)\s+---\s*$"
)


def _intbool(v) -> int:
    return 1 if v else 0


def _csv(v) -> str:
    if not v:
        return ""
    return ",".join(str(x).strip() for x in v)


def _destructive_diff(conn, data_dir: Path) -> list[str]:
    """Return human-readable warnings for rows that would be cascade-deleted."""
    warnings: list[str] = []

    yaml_people = {p["id"] for p in (yaml_io.load(data_dir / "people.yaml") or [])}
    db_people = {row["id"] for row in conn.execute("SELECT id FROM person").fetchall()}
    removed = db_people - yaml_people
    for pid in sorted(removed):
        refs = conn.execute(
            "SELECT COUNT(*) AS n FROM assignment WHERE person_id = ? AND archived = 0", (pid,)
        ).fetchone()["n"]
        if refs:
            warnings.append(f"person '{pid}' removed but has {refs} live assignments")

    yaml_projects = {p["code"] for p in (yaml_io.load(data_dir / "projects.yaml") or [])}
    db_projects = {row["code"] for row in conn.execute("SELECT code FROM project").fetchall()}
    removed_proj = db_projects - yaml_projects
    for code in sorted(removed_proj):
        refs = conn.execute(
            "SELECT COUNT(*) AS n FROM assignment WHERE project_code = ? AND archived = 0", (code,)
        ).fetchone()["n"]
        if refs:
            warnings.append(f"project '{code}' removed but has {refs} live assignments")

    return warnings


def sync(data_dir: Path | None = None, db_path: Path | None = None, *, confirm: bool = False) -> dict:
    data_dir = Path(data_dir) if data_dir else settings.data_dir
    notes_dir = settings.notes_dir
    db.init_db(db_path)

    with db.transaction(db_path) as conn:
        warnings = _destructive_diff(conn, data_dir)
        if warnings and not confirm:
            for w in warnings:
                print(f"[DESTRUCTIVE] {w}", file=sys.stderr)
            print("Pass --confirm to proceed.", file=sys.stderr)
            sys.exit(2)

        # Wipe and re-load (cheap because files are small; keeps logic trivial)
        for table in (
            "notes_fts", "journal_entry",
            "availability", "assignment",
            "project_required_skill", "project",
            "contact", "client",
            "person_skill", "person",
            "office", "skill",
        ):
            conn.execute(f"DELETE FROM {table}")

        # skills
        for s in yaml_io.load(data_dir / "skills.yaml") or []:
            conn.execute(
                "INSERT INTO skill (id, label_es, description, archived) VALUES (?, ?, ?, ?)",
                (s["id"], s["label_es"], s.get("description", ""), _intbool(s.get("archived"))),
            )

        # offices
        for o in yaml_io.load(data_dir / "offices.yaml") or []:
            conn.execute(
                "INSERT INTO office (office_id, city, country, lat, lon, archived) VALUES (?, ?, ?, ?, ?, ?)",
                (o["office_id"], o["city"], o.get("country", ""),
                 float(o.get("lat", 0)), float(o.get("lon", 0)), _intbool(o.get("archived"))),
            )

        # clients
        for c in yaml_io.load(data_dir / "clients.yaml") or []:
            conn.execute(
                """INSERT INTO client (id, name, sector, size, country, status, description, archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (c["id"], c["name"], c.get("sector", ""), c.get("size", ""),
                 c.get("country", ""), c.get("status", "activo"),
                 c.get("description", ""), _intbool(c.get("archived"))),
            )
            for i, k in enumerate(c.get("contacts", []) or []):
                conn.execute(
                    """INSERT INTO contact (client_id, idx, name, role, email, phone)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (c["id"], i, k["name"], k.get("role", ""), k.get("email", ""), k.get("phone", "")),
                )

        # people + person_skill
        for p in yaml_io.load(data_dir / "people.yaml") or []:
            conn.execute(
                """INSERT INTO person (id, full_name, office, city, timezone, languages_csv,
                    base_role, global_level, contractual_fte, start_date, archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p["id"], p["full_name"], p["office"], p.get("city", ""), p.get("timezone", "CET"),
                 _csv(p.get("languages")), p.get("base_role", "pentester"),
                 p["global_level"], float(p.get("contractual_fte", 1.0)),
                 str(p["start_date"]), _intbool(p.get("archived"))),
            )
            for ps in p.get("skills", []) or []:
                conn.execute(
                    """INSERT INTO person_skill (person_id, skill_id, level, last_used_on_project, growth_interest)
                       VALUES (?, ?, ?, ?, ?)""",
                    (p["id"], ps["skill_id"], int(ps.get("level", 0)),
                     ps.get("last_used_on_project"), _intbool(ps.get("growth_interest"))),
                )

        # projects + required_skills
        for pr in yaml_io.load(data_dir / "projects.yaml") or []:
            conn.execute(
                """INSERT INTO project (code, client_alias, type, window_start, window_end,
                    estimated_hours, status, archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (pr["code"], pr["client_alias"], pr["type"], str(pr["window_start"]),
                 str(pr["window_end"]), int(pr.get("estimated_hours", 0)),
                 pr["status"], _intbool(pr.get("archived"))),
            )
            for rs in pr.get("required_skills", []) or []:
                conn.execute(
                    """INSERT INTO project_required_skill (project_code, skill_id, weight, min_level)
                       VALUES (?, ?, ?, ?)""",
                    (pr["code"], rs["skill_id"], int(rs["weight"]), int(rs["min_level"])),
                )

        # assignments
        for a in yaml_io.load(data_dir / "assignments.yaml") or []:
            conn.execute(
                """INSERT OR IGNORE INTO assignment (person_id, project_code, dedication_pct, start, end, role, archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (a["person_id"], a["project_code"], int(a["dedication_pct"]),
                 str(a["start"]), str(a["end"]), a.get("role", "executor"),
                 _intbool(a.get("archived"))),
            )

        # availability
        for av in yaml_io.load(data_dir / "availability.yaml") or []:
            conn.execute(
                """INSERT OR IGNORE INTO availability (person_id, kind, start, end, pct, reason, archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (av["person_id"], av["kind"], str(av["start"]), str(av["end"]),
                 int(av.get("pct", 100)), av.get("reason", ""),
                 _intbool(av.get("archived"))),
            )

        # journal
        for j in yaml_io.load(data_dir / "journal.yaml") or []:
            ts = j["timestamp"]
            conn.execute(
                """INSERT INTO journal_entry (id, timestamp, proposer, kind, payload_json, status,
                    applied_at, applied_by, rejected_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (j["id"], str(ts), j["proposer"], j["kind"], _json_dumps(dict(j.get("payload", {}) or {})),
                 j["status"],
                 str(j["applied_at"]) if j.get("applied_at") else None,
                 j.get("applied_by"),
                 j.get("rejected_reason")),
            )

        # notes_fts (rebuild from markdown)
        _index_notes(conn, notes_dir)

    return {"ok": True, "destructive_warnings": warnings, "confirmed": confirm}


def _index_notes(conn, notes_dir: Path) -> None:
    if not notes_dir.exists():
        return
    mapping = {"persons": "person", "projects": "project", "clients": "client"}
    for sub, entity_type in mapping.items():
        sub_path = notes_dir / sub
        if not sub_path.exists():
            continue
        for md in sub_path.glob("*.md"):
            entity_id = md.stem
            for note in _parse_markdown_notes(md):
                conn.execute(
                    """INSERT INTO notes_fts (entity_type, entity_id, timestamp, author, tags, body)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (entity_type, entity_id, note["timestamp"], note["author"],
                     ",".join(note["tags"]), note["body"]),
                )


def _parse_markdown_notes(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    blocks: list[dict] = []
    current: dict | None = None
    body_lines: list[str] = []
    for raw in text.splitlines():
        m = NOTE_SEP_RE.match(raw)
        if m:
            if current is not None:
                current["body"] = "\n".join(body_lines).strip()
                blocks.append(current)
            tags_raw = m.group("tags").strip()
            current = {
                "timestamp": m.group("ts").strip(),
                "author": m.group("author").strip(),
                "tags": [t.strip() for t in tags_raw.split(",") if t.strip()],
            }
            body_lines = []
        elif current is not None:
            body_lines.append(raw)
    if current is not None:
        current["body"] = "\n".join(body_lines).strip()
        blocks.append(current)
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild SQLite cache from YAML data.")
    parser.add_argument("--confirm", action="store_true", help="Proceed even with destructive diffs")
    args = parser.parse_args()
    t0 = datetime.now(timezone.utc)
    result = sync(confirm=args.confirm)
    dt = (datetime.now(timezone.utc) - t0).total_seconds()
    print(f"sync ok in {dt*1000:.0f}ms — destructive={len(result['destructive_warnings'])}")


if __name__ == "__main__":
    main()
