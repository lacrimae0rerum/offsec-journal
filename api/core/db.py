"""SQLite connection + schema. The DB is a read-cache; YAML is truth.

Tables mirror YAML entity shape plus computed columns used by the heatmap
and skill-gap endpoints. FTS5 virtual table `notes_fts` indexes note bodies.
Schema is idempotent — running init_db() on an existing DB is a no-op.
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

CREATE TABLE IF NOT EXISTS skill (
    id TEXT PRIMARY KEY,
    label_es TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS office (
    office_id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT '',
    lat REAL NOT NULL DEFAULT 0,
    lon REAL NOT NULL DEFAULT 0,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS person (
    id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    office TEXT NOT NULL,
    city TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'CET',
    languages_csv TEXT NOT NULL DEFAULT '',
    base_role TEXT NOT NULL DEFAULT 'pentester',
    global_level TEXT NOT NULL CHECK (global_level IN ('junior','intermediate','senior','master')),
    contractual_fte REAL NOT NULL DEFAULT 1.0,
    start_date TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS person_skill (
    person_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    level INTEGER NOT NULL CHECK (level BETWEEN 0 AND 5),
    last_used_on_project TEXT,
    growth_interest INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (person_id, skill_id),
    FOREIGN KEY (person_id) REFERENCES person(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS client (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT NOT NULL DEFAULT '',
    size TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'activo',
    description TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE,
    UNIQUE (client_id, idx)
);

CREATE TABLE IF NOT EXISTS project (
    code TEXT PRIMARY KEY,
    client_alias TEXT NOT NULL,
    type TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    estimated_hours INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK (status IN ('pipeline','active','closed')),
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS project_required_skill (
    project_code TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    weight INTEGER NOT NULL CHECK (weight BETWEEN 1 AND 3),
    min_level INTEGER NOT NULL CHECK (min_level BETWEEN 1 AND 5),
    PRIMARY KEY (project_code, skill_id),
    FOREIGN KEY (project_code) REFERENCES project(code) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    project_code TEXT NOT NULL,
    dedication_pct INTEGER NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('lead','executor','reviewer','shadow')),
    archived INTEGER NOT NULL DEFAULT 0,
    UNIQUE (person_id, project_code, start)
);

CREATE TABLE IF NOT EXISTS availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('pto','sick','training','overhead','hold')),
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    pct INTEGER NOT NULL DEFAULT 100,
    reason TEXT NOT NULL DEFAULT '',
    archived INTEGER NOT NULL DEFAULT 0,
    UNIQUE (person_id, kind, start)
);

CREATE TABLE IF NOT EXISTS journal_entry (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    proposer TEXT NOT NULL CHECK (proposer IN ('llm','human')),
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','applied','rejected')),
    applied_at TEXT,
    applied_by TEXT,
    rejected_reason TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    entity_type UNINDEXED,
    entity_id UNINDEXED,
    timestamp UNINDEXED,
    author,
    tags,
    body,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE INDEX IF NOT EXISTS idx_assignment_person  ON assignment(person_id);
CREATE INDEX IF NOT EXISTS idx_assignment_project ON assignment(project_code);
CREATE INDEX IF NOT EXISTS idx_availability_person ON availability(person_id);
CREATE INDEX IF NOT EXISTS idx_person_skill_skill ON person_skill(skill_id);
CREATE INDEX IF NOT EXISTS idx_project_status     ON project(status);
CREATE INDEX IF NOT EXISTS idx_journal_status     ON journal_entry(status);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path) if path else settings.db_path
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def transaction(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
