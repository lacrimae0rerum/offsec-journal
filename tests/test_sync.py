"""Sync is idempotent and produces the expected row counts from seed data."""
from api.core import db, sync


def _counts(conn):
    return {
        "person": conn.execute("SELECT COUNT(*) n FROM person").fetchone()["n"],
        "skill": conn.execute("SELECT COUNT(*) n FROM skill").fetchone()["n"],
        "project": conn.execute("SELECT COUNT(*) n FROM project").fetchone()["n"],
        "assignment": conn.execute("SELECT COUNT(*) n FROM assignment").fetchone()["n"],
        "availability": conn.execute("SELECT COUNT(*) n FROM availability").fetchone()["n"],
        "client": conn.execute("SELECT COUNT(*) n FROM client").fetchone()["n"],
        "office": conn.execute("SELECT COUNT(*) n FROM office").fetchone()["n"],
        "journal": conn.execute("SELECT COUNT(*) n FROM journal_entry").fetchone()["n"],
    }


def test_sync_idempotent(tmp_env):
    """Running sync twice should yield the same counts."""
    with db.transaction() as conn:
        first = _counts(conn)
    sync.sync()
    with db.transaction() as conn:
        second = _counts(conn)
    assert first == second


def test_seed_counts(tmp_env):
    with db.transaction() as conn:
        c = _counts(conn)
    # Counts may grow as journal applies land; assert lower bounds instead.
    assert c["skill"] == 20
    assert c["office"] == 4
    assert c["person"] >= 6
    assert c["project"] >= 8
    assert c["client"] >= 8
    assert c["assignment"] >= 11
    assert c["availability"] >= 2
    assert c["journal"] >= 3


def test_person_skills_loaded(tmp_env):
    with db.transaction() as conn:
        fer_skills = conn.execute(
            "SELECT skill_id, level FROM person_skill WHERE person_id = 'fer' ORDER BY skill_id"
        ).fetchall()
    assert len(fer_skills) == 7
    levels = {r["skill_id"]: r["level"] for r in fer_skills}
    assert levels["hacking_active_directory"] == 4
    assert levels["hacking_cloud"] == 2
