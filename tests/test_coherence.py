"""Coherence rules: every level band + the insufficient_skill_coverage override."""
from api.core.coherence import check_person


def _p(**over):
    base = {"id": "x", "global_level": "senior", "archived": False}
    base.update(over)
    return base


def _skills(*levels):
    return [{"skill_id": f"s{i}", "level": lv} for i, lv in enumerate(levels)]


def test_senior_ok_2_high_and_avg():
    person = _p(global_level="senior")
    warnings = check_person(person, _skills(4, 4, 3, 3, 4))
    assert warnings == []


def test_senior_fails_avg_top5():
    person = _p(global_level="senior")
    # high=2 but top-5 avg = (4+4+1+1+1)/5 = 2.2 < 3.5
    warnings = check_person(person, _skills(4, 4, 1, 1, 1))
    assert any(w["rule"] == "senior_insufficient_depth" for w in warnings)


def test_senior_insufficient_coverage_override():
    person = _p(global_level="senior")
    # only 4 skills with level>=1 → coverage rule fires, not numeric
    warnings = check_person(person, _skills(4, 4, 3, 3))
    assert len(warnings) == 1
    assert warnings[0]["rule"] == "insufficient_skill_coverage"


def test_master_requires_3_high():
    person = _p(global_level="master")
    warnings = check_person(person, _skills(4, 4, 3, 3, 3))
    assert any(w["rule"] == "master_insufficient_high_skills" for w in warnings)


def test_intermediate_requires_3_mid():
    person = _p(global_level="intermediate")
    warnings = check_person(person, _skills(3, 3, 2, 1))
    assert any(w["rule"] == "intermediate_insufficient_mid_skills" for w in warnings)


def test_junior_warn_if_high_skills():
    person = _p(global_level="junior")
    warnings = check_person(person, _skills(4, 4, 1))
    assert any(w["rule"] == "junior_with_high_skills" for w in warnings)


def test_junior_clean():
    person = _p(global_level="junior")
    assert check_person(person, _skills(2, 1, 1)) == []
