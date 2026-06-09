"""Shared fixtures for the test suite.

Seed data lives in `tests/fixtures/seed/` with the multi-tenant layout:

    seed/
      teams.yaml               # offsec + infosec
      skills.yaml              # shared
      offsec/*.yaml            # tenant-scoped (all historic seed data lives here)
      infosec/*.yaml           # empty — isolation tests populate it per-test
    notes/
      offsec/persons|projects|clients/*.md
      infosec/persons|projects|clients/*.md

`tmp_env` copies this seed into a tmp dir and points `settings` at it, then
runs `sync()` so the SQLite cache is primed.

Auth: tests interact with the app through fixtures that inject the nginx
Remote-User header + a loopback IP. The DB user table is seeded with four
standard users (2 teams × {admin, member}) by the `seed_users` fixture.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ulid import ULID

from api import config as config_module


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


# =============================================================================
# Environment
# =============================================================================

@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    """Copy seed/ + notes/ into tmp_path and rebind settings paths.

    Runs `sync()` to prime the SQLite cache from YAML. Returns the paths
    (data_dir, notes_dir, db_path) so tests that need raw filesystem access
    can manipulate them directly.

    Also whitelists the TestClient's stub client.host ("testclient") in
    `trusted_proxy_ips` — without this the auth middleware would 403 every
    TestClient request as an untrusted proxy.
    """
    data_dir = tmp_path / "data"
    notes_dir = tmp_path / "notes"
    db_path = tmp_path / "cache.db"

    shutil.copytree(FIXTURES / "seed", data_dir)
    src_notes = FIXTURES / "notes"
    if src_notes.exists():
        shutil.copytree(src_notes, notes_dir)
    else:
        notes_dir.mkdir()

    monkeypatch.setattr(config_module.settings, "data_dir", data_dir)
    monkeypatch.setattr(config_module.settings, "notes_dir", notes_dir)
    monkeypatch.setattr(config_module.settings, "db_path", db_path)
    monkeypatch.setattr(config_module.settings, "trusted_proxy_ips", "127.0.0.1,testclient")

    from api.core import sync as sync_mod
    sync_mod.sync()

    return {"data_dir": data_dir, "notes_dir": notes_dir, "db_path": db_path}


# =============================================================================
# Users (seeded into the `user` table, not the YAML layer)
# =============================================================================

STANDARD_USERS = {
    "offsec_admin":  {"username": "fer",    "team": "offsec",  "role": "admin",  "display": "Fernando"},
    "offsec_member": {"username": "carlos", "team": "offsec",  "role": "member", "display": "Carlos"},
    "infosec_admin": {"username": "ana",    "team": "infosec", "role": "admin",  "display": "Ana"},
    "infosec_member":{"username": "bart",   "team": "infosec", "role": "member", "display": "Bart"},
}


@pytest.fixture
def seed_users(tmp_env):
    """Seed the 4 standard users and return a dict keyed by role+team.

    Each value is a dict {id, username, team, role, display}. Tests that need
    a user with different attrs can still insert ad-hoc via `db.transaction()`.
    """
    from api.core import db

    inserted: dict[str, dict] = {}
    with db.transaction() as conn:
        for key, spec in STANDARD_USERS.items():
            uid = str(ULID())
            conn.execute(
                """INSERT INTO user (id, username, team_id, role, display_name, email)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (uid, spec["username"], spec["team"], spec["role"],
                 spec["display"], f"{spec['username']}@test.local"),
            )
            inserted[key] = {"id": uid, **spec}
    return inserted


# =============================================================================
# HTTP clients (TestClient with Remote-User preset)
# =============================================================================

def _make_client() -> TestClient:
    """Fresh TestClient bound to a freshly-created app. `tmp_env` must have
    run first so the app picks up the monkeypatched settings."""
    from api.main import create_app
    return TestClient(create_app())


@pytest.fixture
def app_client(tmp_env):
    """TestClient with no Remote-User header — use for testing middleware
    failure paths (401 missing, 403 unknown)."""
    return _make_client()


def _client_as(username: str) -> TestClient:
    client = _make_client()
    client.headers.update({
        "Remote-User": username,
        "X-Real-IP": "10.8.0.42",
        "User-Agent": "pytest",
    })
    return client


@pytest.fixture
def offsec_admin_client(seed_users):
    return _client_as(seed_users["offsec_admin"]["username"])


@pytest.fixture
def offsec_member_client(seed_users):
    return _client_as(seed_users["offsec_member"]["username"])


@pytest.fixture
def infosec_admin_client(seed_users):
    return _client_as(seed_users["infosec_admin"]["username"])


@pytest.fixture
def infosec_member_client(seed_users):
    return _client_as(seed_users["infosec_member"]["username"])


# Convenience alias — most historic tests only need "some authenticated user
# on the seeded team" and don't care about role/team semantics. Point it at
# the offsec admin since seed data lives there.
@pytest.fixture
def authelia_client(offsec_admin_client):
    return offsec_admin_client
