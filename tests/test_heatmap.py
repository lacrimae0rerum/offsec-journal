"""Heatmap ISO week logic: year boundaries, short ranges, empty ranges."""
from datetime import date

from api.core import db, queries


def test_iso_weeks_single_week(tmp_env):
    weeks = queries._iso_weeks_between(date(2026, 4, 6), date(2026, 4, 12))
    assert weeks == [(2026, 15)]


def test_iso_weeks_multiple(tmp_env):
    weeks = queries._iso_weeks_between(date(2026, 4, 6), date(2026, 5, 3))
    assert weeks == [(2026, 15), (2026, 16), (2026, 17), (2026, 18)]


def test_iso_weeks_year_boundary():
    """Week 53 of 2026 doesn't exist; Dec 28 2026 is W53 actually — let's use 2025 which has W53."""
    # 2020 had 53 ISO weeks; its Dec 28 2020 falls in W53
    weeks = queries._iso_weeks_between(date(2020, 12, 28), date(2021, 1, 10))
    years = {y for (y, _) in weeks}
    assert 2020 in years
    assert 2021 in years


def test_iso_week_bounds_monday_sunday(tmp_env):
    mon, sun = queries._iso_week_bounds(2026, 15)
    assert mon == date(2026, 4, 6)
    assert sun == date(2026, 4, 12)
    assert mon.isoweekday() == 1
    assert sun.isoweekday() == 7


def test_heatmap_respects_archived(tmp_env):
    """Archived assignments must not contribute to load."""
    with db.transaction() as conn:
        hm = queries.heatmap(conn, "offsec", date(2026, 4, 6), date(2026, 4, 12))
    before = hm["people"]["fer"][0]
    # Archive fer's PT-2026-012 assignment (manual SQL — not the journal path)
    with db.transaction() as conn:
        conn.execute(
            "UPDATE assignment SET archived=1 WHERE person_id='fer' AND project_code='PT-2026-012'"
        )
    with db.transaction() as conn:
        hm = queries.heatmap(conn, "offsec", date(2026, 4, 6), date(2026, 4, 12))
    after = hm["people"]["fer"][0]
    assert after < before


def test_heatmap_zero_when_nobody_assigned(tmp_env):
    with db.transaction() as conn:
        # A far-future week: no assignments land there in the seed
        hm = queries.heatmap(conn, "offsec", date(2028, 6, 1), date(2028, 6, 7))
    for pid, vals in hm["people"].items():
        assert vals == [0]


def test_heatmap_over_allocation_is_summed(tmp_env):
    """tbd_04 had W15: 20% from PT-2026-012. Add another 90% via assign."""
    from api.core import journal
    e = journal.create_entry("assign", {
        "person_id": "tbd_04", "project_code": "RES-2026-001",
        "dedication_pct": 90, "start": "2026-04-06", "end": "2026-04-12", "role": "shadow",
    }, "offsec", proposer="human")
    journal.apply_entry(e["id"], "offsec", applied_by="test")
    with db.transaction() as conn:
        hm = queries.heatmap(conn, "offsec", date(2026, 4, 6), date(2026, 4, 12))
    assert hm["people"]["tbd_04"][0] >= 100  # over allocated
