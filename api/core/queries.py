"""Read queries against SQLite cache + skill-gap / heatmap computations.

Endpoints in api.routes.* call these; this module has no FastAPI imports so
tests can exercise it directly without spinning up an app.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from api.core import db


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---------- People ----------
def list_people(conn, include_archived: bool = False) -> list[dict]:
    q = "SELECT * FROM person" + ("" if include_archived else " WHERE archived = 0")
    people = _rows(conn, q + " ORDER BY id")
    for p in people:
        p["languages"] = p.pop("languages_csv").split(",") if p["languages_csv"] else []
        p["skills"] = _rows(
            conn,
            """SELECT skill_id, level, last_used_on_project, growth_interest
               FROM person_skill WHERE person_id = ? ORDER BY skill_id""",
            (p["id"],),
        )
    return people


def get_person(conn, person_id: str) -> dict | None:
    r = conn.execute("SELECT * FROM person WHERE id = ?", (person_id,)).fetchone()
    if not r:
        return None
    p = dict(r)
    p["languages"] = p.pop("languages_csv").split(",") if p["languages_csv"] else []
    p["skills"] = _rows(
        conn,
        """SELECT skill_id, level, last_used_on_project, growth_interest
           FROM person_skill WHERE person_id = ? ORDER BY skill_id""",
        (person_id,),
    )
    p["assignments"] = _rows(
        conn,
        "SELECT * FROM assignment WHERE person_id = ? AND archived = 0 ORDER BY start DESC",
        (person_id,),
    )
    p["availability"] = _rows(
        conn,
        "SELECT * FROM availability WHERE person_id = ? AND archived = 0 ORDER BY start DESC",
        (person_id,),
    )
    return p


# ---------- Projects ----------
def list_projects(conn, status: str | None = None, include_archived: bool = False) -> list[dict]:
    where = []
    params: list = []
    if status:
        where.append("status = ?")
        params.append(status)
    if not include_archived:
        where.append("archived = 0")
    q = "SELECT * FROM project"
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY status, window_start"
    projects = _rows(conn, q, tuple(params))
    for pr in projects:
        pr["required_skills"] = _rows(
            conn,
            "SELECT skill_id, weight, min_level FROM project_required_skill WHERE project_code = ? ORDER BY skill_id",
            (pr["code"],),
        )
        pr["assignments"] = _rows(
            conn,
            "SELECT * FROM assignment WHERE project_code = ? AND archived = 0",
            (pr["code"],),
        )
    return projects


def get_project(conn, code: str) -> dict | None:
    r = conn.execute("SELECT * FROM project WHERE code = ?", (code,)).fetchone()
    if not r:
        return None
    pr = dict(r)
    pr["required_skills"] = _rows(
        conn,
        "SELECT skill_id, weight, min_level FROM project_required_skill WHERE project_code = ? ORDER BY skill_id",
        (code,),
    )
    pr["assignments"] = _rows(
        conn,
        "SELECT * FROM assignment WHERE project_code = ? AND archived = 0",
        (code,),
    )
    return pr


# ---------- Clients ----------
def list_clients(conn, include_archived: bool = False) -> list[dict]:
    q = "SELECT * FROM client" + ("" if include_archived else " WHERE archived = 0")
    clients = _rows(conn, q + " ORDER BY id")
    for c in clients:
        c["contacts"] = _rows(
            conn,
            "SELECT name, role, email, phone FROM contact WHERE client_id = ? ORDER BY idx",
            (c["id"],),
        )
        c["projects"] = _rows(
            conn,
            """SELECT code, type, window_start, window_end, status
               FROM project WHERE client_alias = ? AND archived = 0 ORDER BY status, window_start""",
            (c["id"],),
        )
    return clients


# ---------- Skills ----------
def list_skills(conn, include_archived: bool = False) -> list[dict]:
    q = "SELECT * FROM skill" + ("" if include_archived else " WHERE archived = 0")
    return _rows(conn, q + " ORDER BY id")


# ---------- Offices / geo ----------
def list_offices(conn) -> list[dict]:
    offices = _rows(conn, "SELECT * FROM office WHERE archived = 0 ORDER BY office_id")
    for o in offices:
        o["people_count"] = conn.execute(
            "SELECT COUNT(*) n FROM person WHERE office = ? AND archived = 0", (o["office_id"],)
        ).fetchone()["n"]
    return offices


# ---------- Journal ----------
def list_journal(conn, status: str | None = None) -> list[dict]:
    q = "SELECT * FROM journal_entry"
    params: tuple = ()
    if status:
        q += " WHERE status = ?"
        params = (status,)
    q += " ORDER BY timestamp DESC"
    return _rows(conn, q, params)


# ---------- Skill gap ----------
def skill_gap(conn, scope: str = "pipeline") -> list[dict]:
    """For each required skill of scope, aggregate (need=max min_level, have=best match level)."""
    projects = _rows(
        conn,
        "SELECT code FROM project WHERE status = ? AND archived = 0",
        (scope,),
    )
    codes = tuple(p["code"] for p in projects)
    if not codes:
        return []
    placeholders = ",".join("?" * len(codes))
    reqs = _rows(
        conn,
        f"""SELECT skill_id, MAX(min_level) AS need, SUM(weight) AS total_weight
            FROM project_required_skill
            WHERE project_code IN ({placeholders})
            GROUP BY skill_id
            ORDER BY total_weight DESC""",
        codes,
    )
    out = []
    for r in reqs:
        best = conn.execute(
            """SELECT MAX(level) AS lvl FROM person_skill ps
               JOIN person p ON p.id = ps.person_id
               WHERE ps.skill_id = ? AND p.archived = 0""",
            (r["skill_id"],),
        ).fetchone()
        have = int(best["lvl"] or 0)
        deficit = max(0, int(r["need"]) - have)
        severity = "rose" if deficit >= 2 else ("amber" if deficit >= 1 else "green")
        out.append({
            "skill_id": r["skill_id"],
            "need": int(r["need"]),
            "have": have,
            "deficit": deficit,
            "weight": int(r["total_weight"]),
            "severity": severity,
        })
    return out


# ---------- Heatmap / dedication ----------
def heatmap(conn, start: date, end: date) -> dict:
    """Return {weeks: [...], people: {id: [pct_per_week,...]}} for [start,end]."""
    people = [r["id"] for r in conn.execute("SELECT id FROM person WHERE archived=0 ORDER BY id")]
    weeks = _iso_weeks_between(start, end)
    per_person: dict[str, list[int]] = {p: [0] * len(weeks) for p in people}
    rows = conn.execute(
        """SELECT person_id, dedication_pct, start, end FROM assignment WHERE archived = 0"""
    ).fetchall()
    for r in rows:
        a_start = date.fromisoformat(r["start"])
        a_end = date.fromisoformat(r["end"])
        for i, (wy, wn) in enumerate(weeks):
            mon, sun = _iso_week_bounds(wy, wn)
            if a_start <= sun and a_end >= mon:
                per_person[r["person_id"]][i] += int(r["dedication_pct"])
    return {
        "weeks": [f"{y}-W{w:02d}" for (y, w) in weeks],
        "people": per_person,
    }


def _iso_weeks_between(start: date, end: date) -> list[tuple[int, int]]:
    """List (year, week) ISO tuples covering start→end inclusive."""
    result: list[tuple[int, int]] = []
    cur = start
    while cur <= end:
        iso = cur.isocalendar()
        tup = (iso.year, iso.week)
        if not result or result[-1] != tup:
            result.append(tup)
        cur = date.fromordinal(cur.toordinal() + 7)
    return result


def _iso_week_bounds(year: int, week: int) -> tuple[date, date]:
    """Monday and Sunday dates for ISO year+week."""
    jan4 = date(year, 1, 4)
    jan4_dow = jan4.isoweekday()  # 1=Mon
    week1_mon = date.fromordinal(jan4.toordinal() - (jan4_dow - 1))
    mon = date.fromordinal(week1_mon.toordinal() + (week - 1) * 7)
    sun = date.fromordinal(mon.toordinal() + 6)
    return mon, sun


# ---------- Search (FTS5) ----------
def search(conn, q: str) -> dict:
    q = q.strip()
    if not q:
        return {"people": [], "projects": [], "notes": [], "stats": {"total": 0}}

    # Simple LIKE on people + projects, FTS on notes.
    like = f"%{q}%"
    people = _rows(
        conn,
        """SELECT id, full_name, office, global_level FROM person
           WHERE archived = 0 AND (id LIKE ? OR full_name LIKE ?)
           ORDER BY id LIMIT 20""",
        (like, like),
    )
    people_by_skill = _rows(
        conn,
        """SELECT DISTINCT p.id, p.full_name, p.office, p.global_level
           FROM person p JOIN person_skill ps ON ps.person_id = p.id
           WHERE p.archived = 0 AND ps.skill_id LIKE ?
           ORDER BY p.id LIMIT 20""",
        (like,),
    )
    # Merge unique
    seen = {x["id"] for x in people}
    for r in people_by_skill:
        if r["id"] not in seen:
            people.append(r)
            seen.add(r["id"])

    projects = _rows(
        conn,
        """SELECT code, client_alias, type, status FROM project
           WHERE archived = 0 AND (code LIKE ? OR client_alias LIKE ?)
           ORDER BY code LIMIT 20""",
        (like, like),
    )

    notes = _rows(
        conn,
        """SELECT entity_type, entity_id, timestamp, author, tags, body
           FROM notes_fts WHERE notes_fts MATCH ? ORDER BY rank LIMIT 20""",
        (_fts_query(q),),
    )
    total = len(people) + len(projects) + len(notes)
    return {"people": people, "projects": projects, "notes": notes, "stats": {"total": total}}


def _fts_query(q: str) -> str:
    """Escape FTS5 special chars and wrap tokens for AND-match."""
    safe = q.replace('"', '""')
    return f'"{safe}"'
