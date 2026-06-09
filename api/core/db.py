"""SQLite connection + schema. The DB is a read-cache; YAML is truth.

Schema structure:

  Identity / tenancy
    team            — 2 rows seeded from data/teams.yaml
    user            — local mapping of Authelia username → team + role
    auth_event      — audit trail of middleware decisions

  Shared catalog
    skill           — technical skills universal to both teams

  Tenant-scoped (every row has team_id FK)
    office, person, person_skill, client, contact, project,
    project_required_skill, assignment, availability, journal_entry

  FTS5
    notes_fts       — full-text index with team_id UNINDEXED column for scoping

`team_id` equals the team slug ("offsec" / "infosec") — chosen over ULIDs
because (a) the set is tiny and stable, (b) SQL dumps and audit logs read
naturally, (c) the YAML directory names already use the slug.

Schema uses `CREATE TABLE IF NOT EXISTS`; upgrading from the pre-multitenant
schema requires deleting cache.db first (sync rebuilds from YAML).
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from api.config import settings


SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ===== Identity / tenancy =====

CREATE TABLE IF NOT EXISTS team (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    team_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin','member')),
    display_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT,
    archived INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (team_id) REFERENCES team(id)
);
CREATE INDEX IF NOT EXISTS idx_user_team     ON user(team_id);
CREATE INDEX IF NOT EXISTS idx_user_username ON user(username);

CREATE TABLE IF NOT EXISTS auth_event (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event TEXT NOT NULL CHECK (event IN (
        'login_success','unknown_user','archived_user','untrusted_proxy',
        'missing_remote_user','role_denied','team_mismatch',
        'dev_bypass','user_autoprovisioned'
    )),
    user_id TEXT,
    username_attempted TEXT,
    team_id TEXT,
    ip TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    detail TEXT,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (team_id) REFERENCES team(id)
);
CREATE INDEX IF NOT EXISTS idx_authevent_ts    ON auth_event(ts);
CREATE INDEX IF NOT EXISTS idx_authevent_team  ON auth_event(team_id, ts);
CREATE INDEX IF NOT EXISTS idx_authevent_event ON auth_event(event);

-- ===== Shared catalog (no team_id) =====

CREATE TABLE IF NOT EXISTS skill (
    id TEXT PRIMARY KEY,
    label_es TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0
);

-- ===== Tenant-scoped =====
-- Every row has team_id FK. created_by_user_id tracks who created via the API
-- (NULL allowed: sync from YAML doesn't know the author).

CREATE TABLE IF NOT EXISTS office (
    office_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT '',
    lat REAL NOT NULL DEFAULT 0,
    lon REAL NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0,
    created_by_user_id TEXT,
    PRIMARY KEY (office_id, team_id),
    FOREIGN KEY (team_id) REFERENCES team(id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
);
CREATE INDEX IF NOT EXISTS idx_office_team ON office(team_id);

CREATE TABLE IF NOT EXISTS person (
    id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    full_name TEXT NOT NULL,
    office TEXT NOT NULL,
    city TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'CET',
    languages_csv TEXT NOT NULL DEFAULT '',
    base_role TEXT NOT NULL DEFAULT 'pentester',
    global_level TEXT NOT NULL CHECK (global_level IN ('junior','intermediate','senior','master')),
    contractual_fte REAL NOT NULL DEFAULT 1.0,
    start_date TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    created_by_user_id TEXT,
    PRIMARY KEY (id, team_id),
    FOREIGN KEY (team_id) REFERENCES team(id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
);
CREATE INDEX IF NOT EXISTS idx_person_team ON person(team_id);

CREATE TABLE IF NOT EXISTS person_skill (
    person_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 5),
    last_used_on_project TEXT,
    growth_interest INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (person_id, team_id, skill_id),
    FOREIGN KEY (person_id, team_id) REFERENCES person(id, team_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skill(id)
);
CREATE INDEX IF NOT EXISTS idx_person_skill_skill ON person_skill(skill_id);

CREATE TABLE IF NOT EXISTS client (
    id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sector TEXT NOT NULL DEFAULT '',
    size TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'activo',
    description TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    created_by_user_id TEXT,
    PRIMARY KEY (id, team_id),
    FOREIGN KEY (team_id) REFERENCES team(id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
);
CREATE INDEX IF NOT EXISTS idx_client_team ON client(team_id);

CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (client_id, team_id) REFERENCES client(id, team_id) ON DELETE CASCADE,
    UNIQUE (client_id, team_id, idx)
);

CREATE TABLE IF NOT EXISTS project (
    code TEXT NOT NULL,
    team_id TEXT NOT NULL,
    client_alias TEXT NOT NULL,
    type TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    estimated_hours INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('pipeline','active','closed')),
    archived INTEGER NOT NULL DEFAULT 0,
    created_by_user_id TEXT,
    PRIMARY KEY (code, team_id),
    FOREIGN KEY (team_id) REFERENCES team(id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
);
CREATE INDEX IF NOT EXISTS idx_project_team   ON project(team_id);
CREATE INDEX IF NOT EXISTS idx_project_status ON project(status);

CREATE TABLE IF NOT EXISTS project_required_skill (
    project_code TEXT NOT NULL,
    team_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    weight INTEGER NOT NULL CHECK (weight BETWEEN 1 AND 3),
    min_level INTEGER NOT NULL CHECK (min_level BETWEEN 1 AND 5),
    PRIMARY KEY (project_code, team_id, skill_id),
    FOREIGN KEY (project_code, team_id) REFERENCES project(code, team_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skill(id)
);

CREATE TABLE IF NOT EXISTS assignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    project_code TEXT NOT NULL,
    dedication_pct INTEGER NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('lead','executor','reviewer','shadow')),
    archived INTEGER NOT NULL DEFAULT 0,
    created_by_user_id TEXT,
    FOREIGN KEY (team_id) REFERENCES team(id),
    FOREIGN KEY (person_id, team_id) REFERENCES person(id, team_id),
    FOREIGN KEY (project_code, team_id) REFERENCES project(code, team_id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id),
    UNIQUE (person_id, team_id, project_code, start)
);
CREATE INDEX IF NOT EXISTS idx_assignment_team    ON assignment(team_id);
CREATE INDEX IF NOT EXISTS idx_assignment_person  ON assignment(person_id, team_id);
CREATE INDEX IF NOT EXISTS idx_assignment_project ON assignment(project_code, team_id);

CREATE TABLE IF NOT EXISTS availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('pto','sick','training','overhead','hold')),
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    pct INTEGER NOT NULL DEFAULT 100,
    reason TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    created_by_user_id TEXT,
    FOREIGN KEY (team_id) REFERENCES team(id),
    FOREIGN KEY (person_id, team_id) REFERENCES person(id, team_id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id),
    UNIQUE (person_id, team_id, kind, start)
);
CREATE INDEX IF NOT EXISTS idx_availability_team   ON availability(team_id);
CREATE INDEX IF NOT EXISTS idx_availability_person ON availability(person_id, team_id);

CREATE TABLE IF NOT EXISTS journal_entry (
    id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    proposer TEXT NOT NULL CHECK (proposer IN ('llm','human')),
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','applied','rejected')),
    applied_at TEXT,
    applied_by TEXT,
    rejected_reason TEXT,
    created_by_user_id TEXT,
    PRIMARY KEY (id, team_id),
    FOREIGN KEY (team_id) REFERENCES team(id),
    FOREIGN KEY (created_by_user_id) REFERENCES user(id)
);
CREATE INDEX IF NOT EXISTS idx_journal_team   ON journal_entry(team_id);
CREATE INDEX IF NOT EXISTS idx_journal_status ON journal_entry(status);

-- ===== FTS5 (tenant-aware) =====
-- CREATE IF NOT EXISTS keeps init_db idempotent under normal operation.
-- Migration of legacy FTS5 schemas (before team_id UNINDEXED) is handled
-- separately in init_db() by a schema check + conditional DROP+CREATE.

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    entity_type UNINDEXED,
    entity_id UNINDEXED,
    team_id UNINDEXED,
    timestamp UNINDEXED,
    author,
    tags,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


FTS_RECREATE_SQL = """
DROP TABLE IF EXISTS notes_fts;
CREATE VIRTUAL TABLE notes_fts USING fts5(
    entity_type UNINDEXED,
    entity_id UNINDEXED,
    team_id UNINDEXED,
    timestamp UNINDEXED,
    author,
    tags,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


AUTH_EVENT_RECREATE_SQL = """
DROP TABLE IF EXISTS auth_event;
CREATE TABLE auth_event (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event TEXT NOT NULL CHECK (event IN (
        'login_success','unknown_user','archived_user','untrusted_proxy',
        'missing_remote_user','role_denied','team_mismatch',
        'dev_bypass','user_autoprovisioned'
    )),
    user_id TEXT,
    username_attempted TEXT,
    team_id TEXT,
    ip TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    detail TEXT,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (team_id) REFERENCES team(id)
);
CREATE INDEX IF NOT EXISTS idx_authevent_ts    ON auth_event(ts);
CREATE INDEX IF NOT EXISTS idx_authevent_team  ON auth_event(team_id, ts);
CREATE INDEX IF NOT EXISTS idx_authevent_event ON auth_event(event);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else settings.db_path
    p.parent.mkdir(parents=True, exist_ok=True)
    newly_created = not p.exists()
    conn = sqlite3.connect(str(p), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if newly_created:
        # Database contains tenant data + audit log; default umask (often 644)
        # leaves it world-readable. Lock it down to owner-only on first create.
        _chmod_owner_only(p)
    return conn


def init_db(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        # Check if notes_fts has the team_id column (added post multi-tenancy).
        # If not, the DB is from a legacy schema — drop and recreate. This is
        # the only destructive path; for correctly-versioned DBs, the CREATE
        # IF NOT EXISTS above is a no-op.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(notes_fts)")}
        if cols and "team_id" not in cols:
            conn.executescript(FTS_RECREATE_SQL)
        # Migrate auth_event CHECK constraint if the legacy enum is in place.
        # Drops audit history (acceptable: events are logged by loguru as well).
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='auth_event'"
        ).fetchone()
        if row and row[0] and "'dev_bypass'" not in row[0]:
            from loguru import logger
            row_count = conn.execute("SELECT COUNT(*) FROM auth_event").fetchone()[0]
            logger.warning(
                "Migrating auth_event CHECK constraint (adding dev_bypass, "
                "user_autoprovisioned). Discarding {} historical event(s); "
                "loguru app.log retains the textual record.",
                row_count,
            )
            conn.executescript(AUTH_EVENT_RECREATE_SQL)
        conn.commit()
    # Lock down newly-created files
    p = Path(path) if path else settings.db_path
    for suffix in ("", "-wal", "-shm"):
        side = p.with_name(p.name + suffix) if suffix else p
        if side.exists():
            _chmod_owner_only(side)


def _chmod_owner_only(path: Path) -> None:
    """Best-effort 0600. Silently ignored on Windows (POSIX chmod is a no-op)."""
    import os
    import stat
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, NotImplementedError):
        pass


@contextmanager
def transaction(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager wrapping a connection in a transaction.

    Rolls back on any exception (including unexpected ones — we want a clean
    slate) and re-raises. The caller sees the original exception type, not a
    wrapper, so they can handle sqlite3.IntegrityError / OperationalError
    specifically upstream.
    """
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
