"""Read queries against SQLite cache + skill-gap / heatmap computations.

All functions that touch tenant-scoped tables take `team_id` as the first
argument. `list_skills` is the only exception — the catalog is shared.

Endpoints in api.routes.* call these; this module has no FastAPI imports so
tests can exercise it directly without spinning up an app.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ---------- People ----------
def list_people(conn: sqlite3.Connection, team_id: str, *,
                include_archived: bool = False) -> list[dict]:
    q = "SELECT * FROM person WHERE team_id = ?"
    params: tuple[Any, ...] = (team_id,)
    if not include_archived:
        q += " AND archived = 0"
    q += " ORDER BY id"
    people = _rows(conn, q, params)
    for p in people:
        p["languages"] = p.pop("languages_csv").split(",") if p["languages_csv"] else []
        p["skills"] = _rows(
            conn,
            """SELECT skill_id, level, last_used_on_project, growth_interest
               FROM person_skill WHERE person_id = ? AND team_id = ?
               ORDER BY skill_id""",
            (p["id"], team_id),
        )
    return people


def list_assignments(conn: sqlite3.Connection, team_id: str, *,
                     include_archived: bool = False) -> list[dict]:
    q = "SELECT * FROM assignment WHERE team_id = ?"
    params: tuple[Any, ...] = (team_id,)
    if not include_archived:
        q += " AND archived = 0"
    return _rows(conn, q, params)


def get_person(conn: sqlite3.Connection, team_id: str, person_id: str) -> dict | None:
    r = conn.execute(
        "SELECT * FROM person WHERE team_id = ? AND id = ?",
        (team_id, person_id),
    ).fetchone()
    if not r:
        return None
    p = dict(r)
    p["languages"] = p.pop("languages_csv").split(",") if p["languages_csv"] else []
    p["skills"] = _rows(
        conn,
        """SELECT skill_id, level, last_used_on_project, growth_interest
           FROM person_skill WHERE person_id = ? AND team_id = ?
           ORDER BY skill_id""",
        (person_id, team_id),
    )
    p["assignments"] = _rows(
        conn,
        """SELECT * FROM assignment
           WHERE person_id = ? AND team_id = ? AND archived = 0
           ORDER BY start DESC""",
        (person_id, team_id),
    )
    p["availability"] = _rows(
        conn,
        """SELECT * FROM availability
           WHERE person_id = ? AND team_id = ? AND archived = 0
           ORDER BY start DESC""",
        (person_id, team_id),
    )
    return p


# ---------- Projects ----------
def list_projects(conn: sqlite3.Connection, team_id: str, *,
                  status: str | None = None,
                  include_archived: bool = False) -> list[dict]:
    where = ["team_id = ?"]
    params: list[Any] = [team_id]
    if status:
        where.append("status = ?")
        params.append(status)
    if not include_archived:
        where.append("archived = 0")
    q = "SELECT * FROM project WHERE " + " AND ".join(where) + " ORDER BY status, window_start"
    projects = _rows(conn, q, tuple(params))
    for pr in projects:
        pr["required_skills"] = _rows(
            conn,
            """SELECT skill_id, weight, min_level
               FROM project_required_skill
               WHERE project_code = ? AND team_id = ?
               ORDER BY skill_id""",
            (pr["code"], team_id),
        )
        pr["assignments"] = _rows(
            conn,
            """SELECT * FROM assignment
               WHERE project_code = ? AND team_id = ? AND archived = 0""",
            (pr["code"], team_id),
        )
    return projects


def get_project(conn: sqlite3.Connection, team_id: str, code: str) -> dict | None:
    r = conn.execute(
        "SELECT * FROM project WHERE team_id = ? AND code = ?",
        (team_id, code),
    ).fetchone()
    if not r:
        return None
    pr = dict(r)
    pr["required_skills"] = _rows(
        conn,
        """SELECT skill_id, weight, min_level
           FROM project_required_skill
           WHERE project_code = ? AND team_id = ?
           ORDER BY skill_id""",
        (code, team_id),
    )
    pr["assignments"] = _rows(
        conn,
        """SELECT * FROM assignment
           WHERE project_code = ? AND team_id = ? AND archived = 0""",
        (code, team_id),
    )
    return pr


# ---------- Clients ----------
def list_clients(conn: sqlite3.Connection, team_id: str, *,
                 include_archived: bool = False) -> list[dict]:
    q = "SELECT * FROM client WHERE team_id = ?"
    params: tuple[Any, ...] = (team_id,)
    if not include_archived:
        q += " AND archived = 0"
    q += " ORDER BY id"
    clients = _rows(conn, q, params)
    for c in clients:
        c["contacts"] = _rows(
            conn,
            """SELECT name, role, email, phone FROM contact
               WHERE client_id = ? AND team_id = ?
               ORDER BY idx""",
            (c["id"], team_id),
        )
        c["projects"] = _rows(
            conn,
            """SELECT code, type, window_start, window_end, status
               FROM project
               WHERE client_alias = ? AND team_id = ? AND archived = 0
               ORDER BY status, window_start""",
            (c["id"], team_id),
        )
    return clients


def get_client(conn: sqlite3.Connection, team_id: str, client_id: str) -> dict | None:
    r = conn.execute(
        "SELECT * FROM client WHERE team_id = ? AND id = ?",
        (team_id, client_id),
    ).fetchone()
    if not r:
        return None
    c = dict(r)
    c["contacts"] = _rows(
        conn,
        """SELECT name, role, email, phone FROM contact
           WHERE client_id = ? AND team_id = ? ORDER BY idx""",
        (client_id, team_id),
    )
    c["projects"] = _rows(
        conn,
        """SELECT code, type, window_start, window_end, status
           FROM project
           WHERE client_alias = ? AND team_id = ? AND archived = 0
           ORDER BY status, window_start""",
        (client_id, team_id),
    )
    return c


# ---------- Skills (shared — no team scoping) ----------
def list_skills(conn: sqlite3.Connection, *,
                include_archived: bool = False) -> list[dict]:
    q = "SELECT * FROM skill" + ("" if include_archived else " WHERE archived = 0")
    return _rows(conn, q + " ORDER BY id")


# ---------- Offices (per-team by decision) ----------
def list_offices(conn: sqlite3.Connection, team_id: str) -> list[dict]:
    offices = _rows(
        conn,
        "SELECT * FROM office WHERE team_id = ? AND archived = 0 ORDER BY office_id",
        (team_id,),
    )
    for o in offices:
        o["people_count"] = conn.execute(
            """SELECT COUNT(*) n FROM person
               WHERE office = ? AND team_id = ? AND archived = 0""",
            (o["office_id"], team_id),
        ).fetchone()["n"]
    return offices


# ---------- Journal ----------
def list_journal(conn: sqlite3.Connection, team_id: str, *,
                 status: str | None = None) -> list[dict]:
    where = ["team_id = ?"]
    params: list[Any] = [team_id]
    if status:
        where.append("status = ?")
        params.append(status)
    q = "SELECT * FROM journal_entry WHERE " + " AND ".join(where) + " ORDER BY timestamp DESC"
    return _rows(conn, q, tuple(params))


# ---------- Skill gap ----------
def skill_gap(conn: sqlite3.Connection, team_id: str, *,
              scope: str = "pipeline") -> list[dict]:
    """For each required skill within the team's project scope, aggregate
    need (max min_level) vs have (best person_skill level in the team)."""
    projects = _rows(
        conn,
        "SELECT code FROM project WHERE team_id = ? AND status = ? AND archived = 0",
        (team_id, scope),
    )
    codes = tuple(p["code"] for p in projects)
    if not codes:
        return []
    placeholders = ",".join("?" * len(codes))
    reqs = _rows(
        conn,
        f"""SELECT skill_id, MAX(min_level) AS need, SUM(weight) AS total_weight
            FROM project_required_skill
            WHERE team_id = ? AND project_code IN ({placeholders})
            GROUP BY skill_id
            ORDER BY total_weight DESC""",
        (team_id, *codes),
    )
    out: list[dict] = []
    for r in reqs:
        best = conn.execute(
            """SELECT MAX(level) AS lvl
               FROM person_skill ps
                 JOIN person p ON p.id = ps.person_id AND p.team_id = ps.team_id
               WHERE ps.skill_id = ? AND ps.team_id = ? AND p.archived = 0""",
            (r["skill_id"], team_id),
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
def heatmap(conn: sqlite3.Connection, team_id: str,
            start: date, end: date) -> dict:
    """{weeks: [...], people: {id: [pct_per_week,...]}} scoped to the team."""
    people = [
        r["id"] for r in conn.execute(
            "SELECT id FROM person WHERE team_id = ? AND archived=0 ORDER BY id",
            (team_id,),
        )
    ]
    weeks = _iso_weeks_between(start, end)
    per_person: dict[str, list[int]] = {p: [0] * len(weeks) for p in people}
    rows = conn.execute(
        """SELECT person_id, dedication_pct, start, end
           FROM assignment
           WHERE team_id = ? AND archived = 0""",
        (team_id,),
    ).fetchall()
    for r in rows:
        a_start = date.fromisoformat(r["start"])
        a_end = date.fromisoformat(r["end"])
        for i, (wy, wn) in enumerate(weeks):
            mon, sun = _iso_week_bounds(wy, wn)
            if a_start <= sun and a_end >= mon:
                if r["person_id"] in per_person:
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


# ---------- Search (FTS5 + LIKE) ----------
_SEARCH_TYPES = ("people", "projects", "notes")


def search(
    conn: sqlite3.Connection,
    team_id: str,
    q: str,
    types: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Full-text search across people, projects and notes, team-scoped.

    Optional filters (all backward-compatible — omitting them keeps the old
    behaviour):
    - types: subset of {"people", "projects", "notes"} to include. None = all.
    - date_from / date_to: ISO dates (YYYY-MM-DD) bounding notes by timestamp.
    - tags: notes must carry at least one of these tags (case-insensitive).
    """
    q = q.strip()
    wanted = set(types) & set(_SEARCH_TYPES) if types is not None else set(_SEARCH_TYPES)
    empty = {"people": [], "projects": [], "notes": [], "stats": {"total": 0}}
    if not q:
        return empty

    like = f"%{q}%"

    people: list = []
    if "people" in wanted:
        people = _rows(
            conn,
            """SELECT id, full_name, office, global_level FROM person
               WHERE team_id = ? AND archived = 0
                 AND (id LIKE ? OR full_name LIKE ?)
               ORDER BY id LIMIT 20""",
            (team_id, like, like),
        )
        people_by_skill = _rows(
            conn,
            """SELECT DISTINCT p.id, p.full_name, p.office, p.global_level
               FROM person p JOIN person_skill ps
                 ON ps.person_id = p.id AND ps.team_id = p.team_id
               WHERE p.team_id = ? AND p.archived = 0 AND ps.skill_id LIKE ?
               ORDER BY p.id LIMIT 20""",
            (team_id, like),
        )
        seen = {x["id"] for x in people}
        for r in people_by_skill:
            if r["id"] not in seen:
                people.append(r)
                seen.add(r["id"])

    projects: list = []
    if "projects" in wanted:
        projects = _rows(
            conn,
            """SELECT code, client_alias, type, status FROM project
               WHERE team_id = ? AND archived = 0
                 AND (code LIKE ? OR client_alias LIKE ?)
               ORDER BY code LIMIT 20""",
            (team_id, like, like),
        )

    notes: list = []
    if "notes" in wanted:
        # FTS5: team_id is an UNINDEXED column, filtered with WHERE. The extra
        # filters (date range over timestamp, tag membership) are appended as
        # plain WHERE conditions so they apply before the LIMIT.
        conds = ["notes_fts MATCH ?", "team_id = ?"]
        params: list = [_fts_query(q), team_id]
        if date_from:
            conds.append("substr(timestamp, 1, 10) >= ?")
            params.append(date_from)
        if date_to:
            conds.append("substr(timestamp, 1, 10) <= ?")
            params.append(date_to)
        clean_tags = [t.strip().lower() for t in (tags or []) if t.strip()]
        if clean_tags:
            tag_clause = " OR ".join(["lower(tags) LIKE ?"] * len(clean_tags))
            conds.append(f"({tag_clause})")
            params.extend(f"%{t}%" for t in clean_tags)
        notes = _rows(
            conn,
            f"""SELECT entity_type, entity_id, timestamp, author, tags, body
                FROM notes_fts
                WHERE {' AND '.join(conds)}
                ORDER BY rank LIMIT 20""",
            tuple(params),
        )

    total = len(people) + len(projects) + len(notes)
    return {"people": people, "projects": projects, "notes": notes, "stats": {"total": total}}


def _fts_query(q: str) -> str:
    """Escape FTS5 special chars and wrap tokens for AND-match."""
    safe = q.replace('"', '""')
    return f'"{safe}"'
