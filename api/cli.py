"""CLI `offsec` — admin ops for teams and users.

Runtime:
    .venv/bin/offsec <noun> <verb> [args]
    python -m api.cli <noun> <verb> [args]

Registered as `offsec` in pyproject.toml. Mutates only the local `user` /
`team` tables in SQLite. Does NOT touch Authelia — passwords and MFA live
there. The onboarding flow for a new user is two steps:

    1) Edit /etc/authelia/users.yml + authelia crypto hash generate argon2
       sudo systemctl reload authelia
    2) offsec users add --username <u> --team <slug> --role <admin|member>

Exit codes: 0 ok, 1 user error (not found, duplicate, bad arg), 2 system error.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

from ulid import ULID

from api.core import db


# =============================================================================
# helpers
# =============================================================================

def _print_table(rows: list[dict], columns: list[str]) -> None:
    """Plain-text aligned table. Empty rows -> prints '(no rows)'."""
    if not rows:
        print("(no rows)")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, "") or "")) for r in rows)) for c in columns}
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("  ".join("-" * widths[c] for c in columns))
    for r in rows:
        print("  ".join(str(r.get(c, "") or "").ljust(widths[c]) for c in columns))


def _team_exists(conn: sqlite3.Connection, slug: str) -> bool:
    return conn.execute("SELECT 1 FROM team WHERE slug = ?", (slug,)).fetchone() is not None


def _list_team_slugs(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT slug FROM team ORDER BY slug")]


def _get_user(conn: sqlite3.Connection, username: str) -> dict | None:
    row = conn.execute(
        """SELECT u.id, u.username, u.team_id, u.role, u.display_name, u.email,
                   u.archived, u.created_at, u.updated_at, u.last_seen_at,
                   t.slug AS team_slug, t.name AS team_name
            FROM user u JOIN team t ON t.id = u.team_id
            WHERE u.username = ?""",
        (username.lower(),),
    ).fetchone()
    return dict(row) if row else None


def _die(msg: str, exit_code: int = 1) -> int:
    print(msg, file=sys.stderr)
    return exit_code


# =============================================================================
# teams
# =============================================================================

def _cmd_teams_list(args: argparse.Namespace) -> int:
    with db.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT slug, name, created_at FROM team ORDER BY slug"
        )]
    _print_table(rows, ["slug", "name", "created_at"])
    return 0


# =============================================================================
# users
# =============================================================================

def _cmd_users_list(args: argparse.Namespace) -> int:
    q = """SELECT u.username, t.slug AS team, u.role, u.archived,
                   u.display_name, u.email, u.last_seen_at
            FROM user u JOIN team t ON t.id = u.team_id"""
    where: list[str] = []
    params: list[str] = []
    with db.connect() as conn:
        if args.team:
            if not _team_exists(conn, args.team):
                return _die(
                    f"team '{args.team}' does not exist. "
                    f"Valid: {', '.join(_list_team_slugs(conn))}"
                )
            where.append("t.slug = ?")
            params.append(args.team)
        if not args.archived:
            where.append("u.archived = 0")
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY t.slug, u.username"
        rows = [dict(r) for r in conn.execute(q, tuple(params))]
    for r in rows:
        r["archived"] = "yes" if r["archived"] else ""
        r["last_seen_at"] = r["last_seen_at"] or "never"
    _print_table(
        rows,
        ["username", "team", "role", "archived", "display_name", "email", "last_seen_at"],
    )
    return 0


def _cmd_users_add(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    if not username:
        return _die("username cannot be empty")
    with db.transaction() as conn:
        if not _team_exists(conn, args.team):
            return _die(
                f"team '{args.team}' does not exist. "
                f"Valid: {', '.join(_list_team_slugs(conn))}"
            )
        existing = _get_user(conn, username)
        if existing is not None:
            state = "archived" if existing["archived"] else "active"
            return _die(
                f"user '{username}' already exists "
                f"(team={existing['team_slug']}, {state}). "
                f"Use unarchive / set-team / set-role to modify."
            )
        conn.execute(
            """INSERT INTO user (id, username, team_id, role, display_name, email)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(ULID()), username, args.team, args.role,
             args.display_name or "", args.email or ""),
        )
    print(f"user '{username}' added (team={args.team}, role={args.role})")
    print(
        f"IMPORTANT: '{username}' must also exist in /etc/authelia/users.yml. "
        "This CLI does NOT sync to Authelia."
    )
    return 0


def _cmd_users_archive(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    with db.transaction() as conn:
        user = _get_user(conn, username)
        if user is None:
            return _die(f"user '{username}' not found")
        if user["archived"]:
            print(f"user '{username}' is already archived")
            return 0
        conn.execute(
            "UPDATE user SET archived = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],),
        )
    print(
        f"user '{username}' archived — future requests will 403 (archived_user)"
    )
    return 0


def _cmd_users_unarchive(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    with db.transaction() as conn:
        user = _get_user(conn, username)
        if user is None:
            return _die(f"user '{username}' not found")
        if not user["archived"]:
            print(f"user '{username}' is not archived")
            return 0
        conn.execute(
            "UPDATE user SET archived = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],),
        )
    print(f"user '{username}' unarchived")
    return 0


def _cmd_users_set_team(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    with db.transaction() as conn:
        if not _team_exists(conn, args.team):
            return _die(
                f"team '{args.team}' does not exist. "
                f"Valid: {', '.join(_list_team_slugs(conn))}"
            )
        user = _get_user(conn, username)
        if user is None:
            return _die(f"user '{username}' not found")
        if user["team_slug"] == args.team:
            print(f"user '{username}' is already in team '{args.team}'")
            return 0
        if not args.yes:
            print(
                f"WARNING: moving '{username}' from '{user['team_slug']}' -> '{args.team}'."
            )
            print(
                "  Data this user created (projects, clients, notes, journal entries)"
            )
            print(
                f"  stays in '{user['team_slug']}'. journal_entry.created_by_user_id"
            )
            print(
                "  keeps pointing at this user but the rows are scoped to the old team."
            )
            try:
                resp = input("  proceed? [y/N] ").strip().lower()
            except EOFError:
                resp = ""
            if resp not in ("y", "yes"):
                print("cancelled")
                return 1
        conn.execute(
            "UPDATE user SET team_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (args.team, user["id"]),
        )
    print(f"user '{username}' moved to team '{args.team}'")
    return 0


def _cmd_users_set_role(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    with db.transaction() as conn:
        user = _get_user(conn, username)
        if user is None:
            return _die(f"user '{username}' not found")
        if user["role"] == args.role:
            print(f"user '{username}' already has role '{args.role}'")
            return 0
        conn.execute(
            "UPDATE user SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (args.role, user["id"]),
        )
    print(f"user '{username}' role: {user['role']} -> {args.role}")
    return 0


def _cmd_users_whoami(args: argparse.Namespace) -> int:
    username = args.username.strip().lower()
    with db.connect() as conn:
        user = _get_user(conn, username)
        if user is None:
            return _die(f"user '{username}' not found")
        print("== user ==")
        for k in ("id", "username", "team_slug", "team_name", "role",
                  "display_name", "email", "created_at", "updated_at",
                  "last_seen_at", "archived"):
            print(f"  {k}: {user.get(k)}")
        print()
        print("== recent auth_event (last 10) ==")
        events = [dict(r) for r in conn.execute(
            """SELECT ts, event, ip, path FROM auth_event
               WHERE user_id = ? OR username_attempted = ?
               ORDER BY ts DESC LIMIT 10""",
            (user["id"], username),
        )]
        _print_table(events, ["ts", "event", "ip", "path"])
    return 0


# =============================================================================
# main / argparse
# =============================================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="offsec", description="OffSec Journal admin CLI"
    )
    subparsers = parser.add_subparsers(dest="noun", required=True)

    # teams
    teams = subparsers.add_parser("teams", help="team ops (read-only)")
    ts = teams.add_subparsers(dest="verb", required=True)
    ts.add_parser("list", help="list teams")

    # users
    users = subparsers.add_parser("users", help="user ops (local table only)")
    us = users.add_subparsers(dest="verb", required=True)

    p = us.add_parser("list", help="list users")
    p.add_argument("--team", help="filter by team slug")
    p.add_argument("--archived", action="store_true",
                   help="include archived users")

    p = us.add_parser("add", help="create a user (app-side only, not Authelia)")
    p.add_argument("--username", required=True)
    p.add_argument("--team", required=True)
    p.add_argument("--role", required=True, choices=["admin", "member"])
    p.add_argument("--email", default="")
    p.add_argument("--display-name", default="")

    p = us.add_parser("archive", help="soft-delete a user (preserves FKs)")
    p.add_argument("--username", required=True)

    p = us.add_parser("unarchive", help="re-enable an archived user")
    p.add_argument("--username", required=True)

    p = us.add_parser("set-team", help="move a user to another team")
    p.add_argument("--username", required=True)
    p.add_argument("--team", required=True)
    p.add_argument("--yes", action="store_true",
                   help="skip interactive confirmation")

    p = us.add_parser("set-role", help="change user role (admin/member)")
    p.add_argument("--username", required=True)
    p.add_argument("--role", required=True, choices=["admin", "member"])

    p = us.add_parser("whoami", help="show user row + recent auth_events (debug)")
    p.add_argument("--username", required=True)

    return parser


DISPATCH = {
    ("teams", "list"): _cmd_teams_list,
    ("users", "list"): _cmd_users_list,
    ("users", "add"): _cmd_users_add,
    ("users", "archive"): _cmd_users_archive,
    ("users", "unarchive"): _cmd_users_unarchive,
    ("users", "set-team"): _cmd_users_set_team,
    ("users", "set-role"): _cmd_users_set_role,
    ("users", "whoami"): _cmd_users_whoami,
}


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    handler = DISPATCH.get((args.noun, args.verb))
    if handler is None:
        parser.error(f"unknown command: {args.noun} {args.verb}")
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
