#!/usr/bin/env python3
"""Round 2 — current/future assignments + aggressive edge cases.

Part A (permanent): give every person an ACTIVE/future assignment (the seed's
windows were Feb-Apr 2026, all past relative to 2026-06-21, so most people show
up with no current load). Creates projects with Jun-Dec windows and assigns the
under-loaded people.

Part B (bug hunting): fire aggressive edge cases the first exercise didn't cover
— malformed id/code (the journal payloads lack the regex the read models have),
empty required strings, invalid emails, same-day ranges, level-0 skills,
over-allocation, archived-person references, assignment reactivation.

Reports SUSPECT findings (accepted-but-shouldn't or late validation). Throwaway
entities use the zz_r2_* prefix and are archived at the end.

Pre-requisite: dev server on 127.0.0.1:8001 with DEV_USER=fer.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

PACE = 1.05
log: list[tuple[str, str, str]] = []
findings: list[str] = []


def _req(method, url, headers, body):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.h = {"Remote-User": "fer", "Content-Type": "application/json"}

    def get(self, path):
        s, t = _req("GET", f"{self.base}/api{path}", self.h, None)
        if s != 200:
            raise RuntimeError(f"GET {path} -> {s}: {t}")
        return json.loads(t)

    def post(self, path, body):
        for _ in range(4):
            s, t = _req("POST", f"{self.base}/api{path}", self.h, body)
            if s == 429:
                time.sleep(6)
                continue
            return s, t
        return s, t

    def ok(self, kind, payload, label):
        s, t = self.post("/journal", {"kind": kind, "payload": payload})
        time.sleep(PACE)
        if s != 200:
            log.append(("FAIL", label, f"create {kind} -> {s}: {t}"))
            return False
        eid = json.loads(t)["id"]
        s, t = self.post(f"/journal/{eid}/apply", {})
        time.sleep(PACE)
        if s != 200:
            log.append(("FAIL", label, f"apply {kind} -> {s}: {t}"))
            return False
        log.append(("OK", label, kind))
        return True

    def reject_at_create(self, kind, payload, label, why):
        s, t = self.post("/journal", {"kind": kind, "payload": payload})
        time.sleep(PACE)
        if s == 400:
            log.append(("GOOD_REJECT", label, f"{kind} rechazado en create"))
            return
        if s != 200:
            log.append(("GOOD_REJECT", label, f"{kind} rechazado ({s})"))
            return
        eid = json.loads(t)["id"]
        sa, ta = self.post(f"/journal/{eid}/apply", {})
        time.sleep(PACE)
        if sa == 200:
            log.append(("SUSPECT", label, f"{kind} ACEPTADO Y APLICADO pese a: {why}"))
            findings.append(f"{label}: {kind} aceptado y aplicado pese a que {why}. Payload: {json.dumps(payload, ensure_ascii=False)}")
        else:
            log.append(("SUSPECT", label, f"{kind} pasó create, falló apply: {ta.strip()[:100]}"))
            findings.append(f"{label}: {kind} validado tarde (apply): {ta.strip()[:100]}")
            self.post(f"/journal/{eid}/reject", {"reason": "round2 cleanup"})
            time.sleep(PACE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    args = ap.parse_args()
    c = Client(args.base)
    try:
        c.get("/auth/me")
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2
    skill = c.get("/skills")[0]["id"]

    # =====================================================================
    # PART A — current/future projects + assignments (permanent)
    # =====================================================================
    print("== A. Carga actual/futura para todas las personas ==")
    new_projects = [
        {"code": "NMB-2026-002", "client_alias": "nimbus_health", "type": "pentest_infra",
         "window_start": "2026-07-01", "window_end": "2026-09-15", "estimated_hours": 300,
         "status": "active", "required_skills": [{"skill_id": "explotacion_servicios_red", "weight": 3, "min_level": 4}]},
        {"code": "VTX-2026-002", "client_alias": "vortex_retail", "type": "pentest_web",
         "window_start": "2026-07-15", "window_end": "2026-10-15", "estimated_hours": 360,
         "status": "active", "required_skills": [{"skill_id": "hacking_web", "weight": 3, "min_level": 4}]},
        {"code": "ACM-2026-003", "client_alias": "acme_corp", "type": "red_team",
         "window_start": "2026-08-01", "window_end": "2026-11-30", "estimated_hours": 520,
         "status": "active", "required_skills": [{"skill_id": "evasion_defensas", "weight": 3, "min_level": 4}]},
        {"code": "ZEN-2026-002", "client_alias": "zenith_gov", "type": "red_team",
         "window_start": "2026-09-01", "window_end": "2026-12-20", "estimated_hours": 480,
         "status": "pipeline", "required_skills": [{"skill_id": "phishing", "weight": 3, "min_level": 4}]},
    ]
    for pr in new_projects:
        c.ok("project_create", pr, f"project_create:{pr['code']}")

    new_assignments = [
        ("bruno_silva", "VTX-2026-002", 60, "2026-07-15", "2026-10-15", "lead"),
        ("elena_costa", "VTX-2026-002", 40, "2026-07-15", "2026-10-15", "shadow"),
        ("carla_mendez", "NMB-2026-002", 70, "2026-07-01", "2026-09-15", "lead"),
        ("fernando_ruiz", "NMB-2026-002", 50, "2026-07-01", "2026-09-15", "executor"),
        ("hugo_marin", "ACM-2026-003", 60, "2026-08-01", "2026-11-30", "lead"),
        ("gabriela_nunes", "ACM-2026-003", 50, "2026-08-01", "2026-11-30", "executor"),
        ("ines_lopes", "ZEN-2026-002", 50, "2026-09-01", "2026-12-20", "executor"),
        ("ana_torres", "ZEN-2026-002", 20, "2026-09-01", "2026-12-20", "reviewer"),
        ("diego_ramos", "ACM-2026-003", 20, "2026-08-01", "2026-11-30", "reviewer"),
    ]
    for pid, code, pct, start, end, role in new_assignments:
        c.ok("assign", {"person_id": pid, "project_code": code, "dedication_pct": pct,
                        "start": start, "end": end, "role": role}, f"assign:{pid}->{code}")

    # =====================================================================
    # PART B — aggressive edge cases
    # =====================================================================
    print("== B. Casos límite agresivos ==")

    # Malformed id/code (read models enforce a regex; do the journal payloads?)
    c.reject_at_create("person_create", {"id": "Bad Id!", "full_name": "X", "office": "madrid",
                                         "start_date": "2026-01-01"},
                       "fmt:person-id-spaces", "el id no respeta ^[a-z][a-z0-9_]*$")
    c.reject_at_create("person_create", {"id": "123abc", "full_name": "X", "office": "madrid",
                                         "start_date": "2026-01-01"},
                       "fmt:person-id-digit", "el id empieza por dígito (regex pide letra inicial)")
    c.reject_at_create("project_create", {"code": "bad-code", "client_alias": "acme_corp",
                                          "type": "pentest_web", "window_start": "2026-07-01",
                                          "window_end": "2026-07-31"},
                       "fmt:project-code-lower", "el code no respeta ^[A-Z]{2,4}-\\d{4}-\\d{3}$")
    c.reject_at_create("project_create", {"code": "ACM-26-1", "client_alias": "acme_corp",
                                          "type": "pentest_web", "window_start": "2026-07-01",
                                          "window_end": "2026-07-31"},
                       "fmt:project-code-short", "el code no respeta el formato de 4+3 dígitos")
    c.reject_at_create("skill_catalog_create", {"id": "Not Snake", "label_es": "X"},
                       "fmt:skill-id", "el id de skill no es snake_case")

    # Empty required strings
    c.reject_at_create("person_create", {"id": "zz_r2_empty", "full_name": "", "office": "madrid",
                                         "start_date": "2026-01-01"},
                       "empty:person-name", "full_name está vacío")
    c.reject_at_create("client_create", {"id": "zz_r2_empty_cli", "name": ""},
                       "empty:client-name", "name está vacío")

    # Invalid email in contact
    c.reject_at_create("contact_add", {"client_id": "acme_corp", "name": "Bad Email",
                                       "email": "not-an-email"},
                       "fmt:contact-email", "el email no tiene formato válido")

    # Reference an archived person (zz_temp_person archived in round 1)
    c.reject_at_create("assign", {"person_id": "zz_temp_person", "project_code": "INT-2026-001",
                                  "dedication_pct": 10, "start": "2026-07-01", "end": "2026-07-10"},
                       "ref:assign-archived-person", "la persona está archivada")

    # ---- Cases that SHOULD be accepted (valid but unusual) — on throwaway entities ----
    print("== B2. Casos válidos poco comunes (deben aceptarse) ==")
    if c.ok("client_create", {"id": "zz_r2_client", "name": "ZZ R2 Client"}, "zz:client"):
        if c.ok("project_create", {"code": "ZZR-2026-001", "client_alias": "zz_r2_client",
                                   "type": "internal", "window_start": "2026-07-01",
                                   "window_end": "2026-07-01", "status": "pipeline"},  # same-day window
                "valid:project-same-day-window"):
            # same-day assignment, 0% dedication
            c.ok("assign", {"person_id": "javier_soto", "project_code": "ZZR-2026-001",
                            "dedication_pct": 0, "start": "2026-07-01", "end": "2026-07-01",
                            "role": "shadow"}, "valid:assign-0pct-sameday")
            # reactivation: unassign then re-assign same triple (handler should revive)
            c.ok("unassign", {"person_id": "javier_soto", "project_code": "ZZR-2026-001"},
                 "valid:unassign-for-reactivation")
            c.ok("assign", {"person_id": "javier_soto", "project_code": "ZZR-2026-001",
                            "dedication_pct": 15, "start": "2026-07-01", "end": "2026-07-01",
                            "role": "executor"}, "valid:assign-reactivation")
            c.ok("project_archive", {"code": "ZZR-2026-001", "archived": True}, "zz:project-archive")
        c.ok("client_archive", {"id": "zz_r2_client", "archived": True}, "zz:client-archive")

    # level-0 skill (removes/zeroes a skill — valid, ge=0)
    c.ok("skill_update", {"person_id": "javier_soto", "skill_id": skill, "level": 0},
         "valid:skill-level-0")

    # unicode name (valid)
    c.ok("person_update", {"id": "javier_soto", "full_name": "Javier Soto Núñez"},
         "valid:unicode-name")

    # =====================================================================
    # PART C — over-allocation probe (does coherence catch >100% overlap?)
    # =====================================================================
    print("== C. Sonda de sobre-asignación ==")
    # carla is now 70% on NMB-2026-002 (Jul-Sep). Add 60% overlapping -> 130%.
    c.ok("assign", {"person_id": "carla_mendez", "project_code": "VTX-2026-002",
                    "dedication_pct": 60, "start": "2026-07-15", "end": "2026-09-15",
                    "role": "executor"}, "overalloc:carla-130pct")
    coh = c.get("/coherence")
    warns = coh.get("warnings", []) if isinstance(coh, dict) else coh
    over = [w for w in warns if "alloc" in str(w).lower() or "100" in str(w) or "sobre" in str(w).lower()]
    if over:
        log.append(("OK", "overalloc:detected", f"coherence detecta sobre-asignación: {over}"))
    else:
        findings.append("over-allocation: carla queda al 130% (70% NMB-002 + 60% VTX-002 solapados Jul-Sep) y /api/coherence NO emite ninguna advertencia de sobre-asignación. Posible regla de coherencia ausente.")
        log.append(("SUSPECT", "overalloc:undetected", "coherence no detecta el 130% solapado"))

    # ----- Summary -----
    cats = {}
    for cat, _, _ in log:
        cats[cat] = cats.get(cat, 0) + 1
    print("\n" + "=" * 64)
    print("ROUND 2 SUMMARY")
    for cat in ("OK", "GOOD_REJECT", "SUSPECT", "FAIL"):
        if cats.get(cat):
            print(f"  {cat}: {cats[cat]}")
    for cat in ("FAIL", "SUSPECT"):
        items = [x for x in log if x[0] == cat]
        if items:
            print(f"\n{cat}:")
            for _, label, detail in items:
                print(f"  [{cat}] {label}: {detail}")
    if findings:
        print("\nHALLAZGOS (posibles bugs):")
        for f in findings:
            print(f"  [!] {f}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
