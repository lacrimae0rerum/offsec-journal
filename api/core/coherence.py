"""Coherence rules: global_level ↔ skills. Warnings are non-blocking.

Rules (from prompt, section "Check coherencia"):
  master       ≥3 skills level ≥4
  senior       ≥2 skills level ≥4 AND avg top-5 (level≥1) ≥3.5
  intermediate ≥3 skills level ≥3
  junior       warn if ≥2 skills level ≥4
  special      <5 PersonSkill with level≥1 → "insufficient_skill_coverage"
               (supersedes numeric check for senior/master)
"""
from __future__ import annotations

from typing import TypedDict


class Warning(TypedDict):
    person_id: str
    rule: str
    detail: str
    severity: str  # "warning"


def check_person(person: dict, skills: list[dict]) -> list[Warning]:
    """Return 0-N warnings for a person. `skills` = [{skill_id, level}, ...]."""
    out: list[Warning] = []
    level = person.get("global_level")
    pid = person["id"]
    scored = [s for s in skills if int(s.get("level", 0)) >= 1]
    n_scored = len(scored)
    levels_desc = sorted((int(s["level"]) for s in scored), reverse=True)
    top5_avg = (sum(levels_desc[:5]) / len(levels_desc[:5])) if levels_desc else 0.0
    high = sum(1 for s in scored if int(s["level"]) >= 4)
    mid  = sum(1 for s in scored if int(s["level"]) >= 3)

    if level in ("senior", "master") and n_scored < 5:
        out.append({
            "person_id": pid,
            "rule": "insufficient_skill_coverage",
            "detail": f"Marcado {level} pero sólo {n_scored} PersonSkill con level≥1 (regla pide ≥5).",
            "severity": "warning",
        })
        return out  # overrides numeric rule below

    if level == "master" and high < 3:
        out.append({
            "person_id": pid,
            "rule": "master_insufficient_high_skills",
            "detail": f"master requiere ≥3 skills level≥4; actuales: {high}.",
            "severity": "warning",
        })
    if level == "senior" and (high < 2 or top5_avg < 3.5):
        out.append({
            "person_id": pid,
            "rule": "senior_insufficient_depth",
            "detail": f"senior requiere ≥2 skills L≥4 y avg top-5 ≥3.5; high={high}, avg={top5_avg:.2f}.",
            "severity": "warning",
        })
    if level == "intermediate" and mid < 3:
        out.append({
            "person_id": pid,
            "rule": "intermediate_insufficient_mid_skills",
            "detail": f"intermediate requiere ≥3 skills L≥3; actuales: {mid}.",
            "severity": "warning",
        })
    if level == "junior" and high >= 2:
        out.append({
            "person_id": pid,
            "rule": "junior_with_high_skills",
            "detail": f"junior pero tiene {high} skills L≥4. Considerar intermediate.",
            "severity": "warning",
        })
    return out


def check_overallocation(
    people: list[dict],
    assignments_by_person: dict[str, list[dict]],
) -> list[Warning]:
    """Warn when a person's active assignments overlap in time and their combined
    dedication exceeds 100%.

    Peak overlap always occurs on some assignment's start date, so we sample the
    aggregate dedication at each start and report the worst window per person.
    """
    out: list[Warning] = []
    for p in people:
        if p.get("archived"):
            continue
        rows = [
            a for a in assignments_by_person.get(p["id"], [])
            if not a.get("archived") and a.get("start") and a.get("end")
        ]
        worst_pct = 0
        worst_date: str | None = None
        for sample in rows:
            d = sample["start"]
            total = sum(
                int(a.get("dedication_pct", 0))
                for a in rows
                if a["start"] <= d <= a["end"]
            )
            if total > worst_pct:
                worst_pct, worst_date = total, d
        if worst_pct > 100:
            out.append({
                "person_id": p["id"],
                "rule": "over_allocation",
                "detail": f"Sobre-asignación: {worst_pct}% de dedicación agregada en "
                          f"asignaciones solapadas a fecha {worst_date} (máximo 100%).",
                "severity": "warning",
            })
    return out


def check_all(
    people: list[dict],
    skills_by_person: dict[str, list[dict]],
    assignments_by_person: dict[str, list[dict]] | None = None,
) -> list[Warning]:
    warnings: list[Warning] = []
    for p in people:
        if p.get("archived"):
            continue
        warnings.extend(check_person(p, skills_by_person.get(p["id"], [])))
    if assignments_by_person is not None:
        warnings.extend(check_overallocation(people, assignments_by_person))
    return warnings
