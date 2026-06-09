"""Rebuild SQLite cache from YAML source-of-truth (multi-team).

Walks data/teams.yaml, data/skills.yaml (shared) and each team's folder
(data/<slug>/*.yaml) populating tables with team_id inyected from the path.

Idempotent: running twice is a no-op. Destructive diffs (entity removed from
YAML but referenced by live rows in DB) require `--confirm` to proceed.

Atomicity: the entire wipe-and-reload runs inside a single SQLite transaction
(see `db.transaction()`). SQLite in WAL mode keeps readers consistent against
the pre-commit snapshot until COMMIT lands, so concurrent queries during
sync() see either the old state or the new state — never a half-built DB.

Users and auth_events are NOT touched by sync — users live outside YAML (the
CLI manages them) and auth_events are append-only runtime data.

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


# ---------- destructive diff ----------
def _destructive_diff(conn, data_dir: Path, team_slugs: list[str]) -> list[str]:
    """Warn if a row in DB would be cascade-orphaned by its YAML disappearing."""
    warnings: list[str] = []
    for slug in team_slugs:
        yaml_people = {
            p["id"] for p in (yaml_io.load(yaml_io.tenant_path(slug, "people", data_dir)) or [])
        }
        db_people = {
            row["id"] for row in conn.execute(
                "SELECT id FROM person WHERE team_id = ?", (slug,)
            ).fetchall()
        }
        for pid in sorted(db_people - yaml_people):
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM assignment "
                "WHERE person_id = ? AND team_id = ? AND archived = 0",
                (pid, slug),
            ).fetchone()["n"]
            if n:
                warnings.append(f"[{slug}] person '{pid}' removed but has {n} live assignments")

        yaml_projects = {
            p["code"] for p in (yaml_io.load(yaml_io.tenant_path(slug, "projects", data_dir)) or [])
        }
        db_projects = {
            row["code"] for row in conn.execute(
                "SELECT code FROM project WHERE team_id = ?", (slug,)
            ).fetchall()
        }
        for code in sorted(db_projects - yaml_projects):
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM assignment "
                "WHERE project_code = ? AND team_id = ? AND archived = 0",
                (code, slug),
            ).fetchone()["n"]
            if n:
                warnings.append(f"[{slug}] project '{code}' removed but has {n} live assignments")
    return warnings


# ---------- sync ----------
def sync(
    data_dir: Path | None = None,
    db_path: Path | None = None,
    *,
    confirm: bool = False,
) -> dict:
    data_dir = Path(data_dir) if data_dir else settings.data_dir
    notes_dir = settings.notes_dir
    db.init_db(db_path)

    # Load teams.yaml before opening the transaction so a missing file fails fast.
    teams = yaml_io.load(yaml_io.shared_path("teams", data_dir)) or []
    if not teams:
        raise RuntimeError(
            f"teams.yaml missing or empty at {yaml_io.shared_path('teams', data_dir)}"
        )
    team_slugs = [t["slug"] for t in teams]

    with db.transaction(db_path) as conn:
        warnings = _destructive_diff(conn, data_dir, team_slugs)
        if warnings and not confirm:
            for w in warnings:
                print(f"[DESTRUCTIVE] {w}", file=sys.stderr)
            print("Pass --confirm to proceed.", file=sys.stderr)
            sys.exit(2)

        # Wipe-and-reload from YAML. Order matters for FK cascades: children
        # before parents. `team` is NOT wiped — the `user` table FKs into it,
        # so we UPSERT teams in-place and leave existing users untouched.
        # `user` and `auth_event` are also preserved (not YAML-sourced).
        for table in (
            "notes_fts", "journal_entry",
            "availability", "assignment",
            "project_required_skill", "project",
            "contact", "client",
            "person_skill", "person",
            "office", "skill",
        ):
            conn.execute(f"DELETE FROM {table}")

        # Teams: UPSERT so user.team_id FKs stay valid across syncs
        for t in teams:
            conn.execute(
                """INSERT INTO team (id, slug, name) VALUES (?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET slug=excluded.slug, name=excluded.name""",
                (t["slug"], t["slug"], t["name"]),
            )

        # Shared skills catalog
        for s in yaml_io.load(yaml_io.shared_path("skills", data_dir)) or []:
            conn.execute(
                "INSERT INTO skill (id, label_es, description, archived) VALUES (?, ?, ?, ?)",
                (s["id"], s["label_es"], s.get("description", ""), _intbool(s.get("archived"))),
            )

        # Per-team entities
        for slug in team_slugs:
            _sync_team(conn, data_dir, slug)

        _index_notes(conn, notes_dir, team_slugs)

    return {
        "ok": True,
        "teams": team_slugs,
        "destructive_warnings": warnings,
        "confirmed": confirm,
    }


def _sync_team(conn, data_dir: Path, slug: str) -> None:
    # Offices (per-team by decision)
    for o in yaml_io.load(yaml_io.tenant_path(slug, "offices", data_dir)) or []:
        conn.execute(
            """INSERT INTO office (office_id, team_id, city, country, lat, lon, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (o["office_id"], slug, o["city"], o.get("country", ""),
             float(o.get("lat", 0)), float(o.get("lon", 0)), _intbool(o.get("archived"))),
        )

    # Clients + embedded contacts
    for c in yaml_io.load(yaml_io.tenant_path(slug, "clients", data_dir)) or []:
        conn.execute(
            """INSERT INTO client (id, team_id, name, sector, size, country, status,
                description, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (c["id"], slug, c["name"], c.get("sector", ""), c.get("size", ""),
             c.get("country", ""), c.get("status", "activo"),
             c.get("description", ""), _intbool(c.get("archived"))),
        )
        for i, k in enumerate(c.get("contacts", []) or []):
            conn.execute(
                """INSERT INTO contact (client_id, team_id, idx, name, role, email, phone)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (c["id"], slug, i, k["name"], k.get("role", ""),
                 k.get("email", ""), k.get("phone", "")),
            )

    # People + embedded skills
    for p in yaml_io.load(yaml_io.tenant_path(slug, "people", data_dir)) or []:
        conn.execute(
            """INSERT INTO person (id, team_id, full_name, office, city, timezone, languages_csv,
                base_role, global_level, contractual_fte, start_date, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["id"], slug, p["full_name"], p["office"], p.get("city", ""),
             p.get("timezone", "CET"), _csv(p.get("languages")),
             p.get("base_role", "pentester"), p["global_level"],
             float(p.get("contractual_fte", 1.0)), str(p["start_date"]),
             _intbool(p.get("archived"))),
        )
        for ps in p.get("skills", []) or []:
            conn.execute(
                """INSERT INTO person_skill
                      (person_id, team_id, skill_id, level, last_used_on_project, growth_interest)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (p["id"], slug, ps["skill_id"], int(ps.get("level", 0)),
                 ps.get("last_used_on_project"), _intbool(ps.get("growth_interest"))),
            )

    # Projects + required skills
    for pr in yaml_io.load(yaml_io.tenant_path(slug, "projects", data_dir)) or []:
        conn.execute(
            """INSERT INTO project (code, team_id, client_alias, type, window_start, window_end,
                estimated_hours, status, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pr["code"], slug, pr["client_alias"], pr["type"],
             str(pr["window_start"]), str(pr["window_end"]),
             int(pr.get("estimated_hours", 0)), pr["status"],
             _intbool(pr.get("archived"))),
        )
        for rs in pr.get("required_skills", []) or []:
            conn.execute(
                """INSERT INTO project_required_skill
                      (project_code, team_id, skill_id, weight, min_level)
                   VALUES (?, ?, ?, ?, ?)""",
                (pr["code"], slug, rs["skill_id"], int(rs["weight"]), int(rs["min_level"])),
            )

    # Assignments
    for a in yaml_io.load(yaml_io.tenant_path(slug, "assignments", data_dir)) or []:
        conn.execute(
            """INSERT OR IGNORE INTO assignment
                  (team_id, person_id, project_code, dedication_pct, start, end, role, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (slug, a["person_id"], a["project_code"], int(a["dedication_pct"]),
             str(a["start"]), str(a["end"]), a.get("role", "executor"),
             _intbool(a.get("archived"))),
        )

    # Availability
    for av in yaml_io.load(yaml_io.tenant_path(slug, "availability", data_dir)) or []:
        conn.execute(
            """INSERT OR IGNORE INTO availability
                  (team_id, person_id, kind, start, end, pct, reason, archived)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (slug, av["person_id"], av["kind"], str(av["start"]), str(av["end"]),
             int(av.get("pct", 100)), av.get("reason", ""),
             _intbool(av.get("archived"))),
        )

    # Journal
    for j in yaml_io.load(yaml_io.tenant_path(slug, "journal", data_dir)) or []:
        conn.execute(
            """INSERT INTO journal_entry (id, team_id, timestamp, proposer, kind, payload_json,
                status, applied_at, applied_by, rejected_reason, created_by_user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (j["id"], slug, str(j["timestamp"]), j["proposer"], j["kind"],
             _json_dumps(dict(j.get("payload", {}) or {})),
             j["status"],
             str(j["applied_at"]) if j.get("applied_at") else None,
             j.get("applied_by"),
             j.get("rejected_reason"),
             j.get("created_by_user_id")),
        )


# ---------- notes FTS ----------
def _index_notes(conn, notes_dir: Path, team_slugs: list[str]) -> None:
    if not notes_dir.exists():
        return
    mapping = {"persons": "person", "projects": "project", "clients": "client"}
    for slug in team_slugs:
        team_root = notes_dir / slug
        if not team_root.exists():
            continue
        for sub, entity_type in mapping.items():
            sub_path = team_root / sub
            if not sub_path.exists():
                continue
            for md in sub_path.glob("*.md"):
                entity_id = md.stem
                for note in _parse_markdown_notes(md):
                    conn.execute(
                        """INSERT INTO notes_fts
                              (entity_type, entity_id, team_id, timestamp, author, tags, body)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (entity_type, entity_id, slug, note["timestamp"], note["author"],
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
    parser.add_argument("--confirm", action="store_true",
                        help="Proceed even with destructive diffs")
    args = parser.parse_args()
    t0 = datetime.now(timezone.utc)
    result = sync(confirm=args.confirm)
    dt = (datetime.now(timezone.utc) - t0).total_seconds()
    print(
        f"sync ok in {dt*1000:.0f}ms — teams={','.join(result['teams'])} "
        f"destructive={len(result['destructive_warnings'])}"
    )


if __name__ == "__main__":
    main()
