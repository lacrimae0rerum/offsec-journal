"""CLI `offsec` — covers dispatch, validations, exit codes, case-insensitivity.

Runs `api.cli.main()` in-process with monkeypatched sys.argv. `capsys`
captures stdout/stderr. `pytest.raises(SystemExit)` traps the exit() at the
end of main(). Separate tests for the stdin-driven `set-team` prompt use
`monkeypatch.setattr('builtins.input', ...)`.

Using in-process invocation (not subprocess) so the monkeypatched settings
from `tmp_env` apply — subprocess would spawn a fresh interpreter and hit the
real .env paths.
"""
from __future__ import annotations

import pytest

from api.cli import main
from api.core import db


def _run(monkeypatch, capsys, *args) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.argv", ["offsec", *args])
    with pytest.raises(SystemExit) as exc:
        main()
    captured = capsys.readouterr()
    code = exc.value.code if exc.value.code is not None else 0
    return code, captured.out, captured.err


# =============================================================================
# teams list
# =============================================================================

def test_teams_list_shows_both(tmp_env, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "teams", "list")
    assert code == 0
    assert "offsec" in out and "infosec" in out


# =============================================================================
# users add / list
# =============================================================================

def test_users_add_inserts_row(tmp_env, monkeypatch, capsys):
    code, out, _ = _run(
        monkeypatch, capsys,
        "users", "add",
        "--username", "new_admin",
        "--team", "offsec",
        "--role", "admin",
        "--email", "n@test.local",
    )
    assert code == 0
    assert "added" in out
    assert "Authelia" in out  # warning about two-step flow
    with db.connect() as conn:
        row = conn.execute(
            "SELECT team_id, role, email FROM user WHERE username = 'new_admin'"
        ).fetchone()
    assert row["team_id"] == "offsec"
    assert row["role"] == "admin"
    assert row["email"] == "n@test.local"


def test_users_add_duplicate_fails(tmp_env, seed_users, monkeypatch, capsys):
    # fer already seeded by seed_users fixture
    code, _, err = _run(
        monkeypatch, capsys,
        "users", "add", "--username", "fer", "--team", "offsec", "--role", "admin",
    )
    assert code == 1
    assert "already exists" in err


def test_users_add_bad_team_fails(tmp_env, monkeypatch, capsys):
    code, _, err = _run(
        monkeypatch, capsys,
        "users", "add", "--username", "x", "--team", "badteam", "--role", "admin",
    )
    assert code == 1
    assert "does not exist" in err


def test_users_add_case_insensitive(tmp_env, monkeypatch, capsys):
    _run(
        monkeypatch, capsys,
        "users", "add", "--username", "UPPER", "--team", "offsec", "--role", "member",
    )
    with db.connect() as conn:
        row = conn.execute(
            "SELECT username FROM user WHERE username = 'upper'"
        ).fetchone()
    assert row is not None  # stored lowercased


def test_users_list_filters_by_team(tmp_env, seed_users, monkeypatch, capsys):
    _, out, _ = _run(monkeypatch, capsys, "users", "list", "--team", "infosec")
    assert "ana" in out
    assert "fer" not in out


def test_users_list_hides_archived_by_default(tmp_env, seed_users, monkeypatch, capsys):
    # Archive carlos
    _run(monkeypatch, capsys, "users", "archive", "--username", "carlos")
    # Default list shouldn't show him
    _, out, _ = _run(monkeypatch, capsys, "users", "list")
    assert "carlos" not in out
    # With --archived he appears
    _, out2, _ = _run(monkeypatch, capsys, "users", "list", "--archived")
    assert "carlos" in out2


# =============================================================================
# archive / unarchive / set-role
# =============================================================================

def test_users_archive_and_unarchive_roundtrip(tmp_env, seed_users, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "users", "archive", "--username", "fer")
    assert code == 0 and "archived" in out
    with db.connect() as conn:
        assert conn.execute(
            "SELECT archived FROM user WHERE username='fer'"
        ).fetchone()["archived"] == 1
    code, out, _ = _run(monkeypatch, capsys, "users", "unarchive", "--username", "fer")
    assert code == 0 and "unarchived" in out
    with db.connect() as conn:
        assert conn.execute(
            "SELECT archived FROM user WHERE username='fer'"
        ).fetchone()["archived"] == 0


def test_users_archive_user_not_found_returns_1(tmp_env, monkeypatch, capsys):
    code, _, err = _run(monkeypatch, capsys, "users", "archive", "--username", "ghost")
    assert code == 1
    assert "not found" in err


def test_users_set_role_updates(tmp_env, seed_users, monkeypatch, capsys):
    code, out, _ = _run(
        monkeypatch, capsys,
        "users", "set-role", "--username", "fer", "--role", "member",
    )
    assert code == 0
    assert "admin -> member" in out
    with db.connect() as conn:
        assert conn.execute(
            "SELECT role FROM user WHERE username='fer'"
        ).fetchone()["role"] == "member"


# =============================================================================
# set-team with and without confirmation
# =============================================================================

def test_users_set_team_with_yes_skips_prompt(tmp_env, seed_users, monkeypatch, capsys):
    code, out, _ = _run(
        monkeypatch, capsys,
        "users", "set-team", "--username", "fer", "--team", "infosec", "--yes",
    )
    assert code == 0
    assert "moved" in out


def test_users_set_team_prompt_declined(tmp_env, seed_users, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    code, out, _ = _run(
        monkeypatch, capsys,
        "users", "set-team", "--username", "fer", "--team", "infosec",
    )
    assert code == 1
    assert "cancelled" in out


def test_users_set_team_prompt_accepted(tmp_env, seed_users, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    code, out, _ = _run(
        monkeypatch, capsys,
        "users", "set-team", "--username", "fer", "--team", "infosec",
    )
    assert code == 0
    assert "moved" in out
    with db.connect() as conn:
        assert conn.execute(
            "SELECT team_id FROM user WHERE username='fer'"
        ).fetchone()["team_id"] == "infosec"


# =============================================================================
# whoami + argparse validation
# =============================================================================

def test_users_whoami_prints_row_and_events(tmp_env, seed_users, monkeypatch, capsys):
    code, out, _ = _run(monkeypatch, capsys, "users", "whoami", "--username", "fer")
    assert code == 0
    assert "team_slug" in out and "offsec" in out


def test_argparse_rejects_invalid_role(tmp_env, monkeypatch, capsys):
    # argparse exits with 2 on invalid choices BEFORE main() dispatch runs
    monkeypatch.setattr("sys.argv", [
        "offsec", "users", "add",
        "--username", "x", "--team", "offsec", "--role", "overlord",
    ])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
