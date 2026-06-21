#!/usr/bin/env python3
"""Exhaustive journal exercise for OffSec Journal — coverage + bug hunting.

Goal 1 (coverage): drive EVERY journal kind through the real HTTP API, including
the ones the seed didn't touch (unassign, *_update, *_archive, contact
update/remove, office_*, skill_label_update). Functional cases are reversible or
use throwaway `zz_*` entities left archived, so the live dataset stays coherent.

Goal 2 (bug hunting): fire deliberate edge cases (inverted dates, duplicates,
out-of-range indices, over-allocation, archived references...) and report whether
the server rejected them correctly (clear 400 at create) or let them through /
failed with an opaque error at apply — the latter being a likely bug.

Pre-requisite: dev server on 127.0.0.1:8001 with DEV_USER=fer.

Usage: python3 scripts/exercise_journal.py
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

WRITE_PACING_S = 1.05

# (category, label, detail) — category in {OK, COVERAGE, GOOD_REJECT, SUSPECT, FAIL}
log: list[tuple[str, str, str]] = []
findings: list[str] = []  # human-readable suspected bugs


def _req(method: str, url: str, headers: dict, body: dict | None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.h = {"Remote-User": "fer", "Content-Type": "application/json"}

    def get(self, path: str):
        s, t = _req("GET", f"{self.base}/api{path}", self.h, None)
        if s != 200:
            raise RuntimeError(f"GET {path} -> {s}: {t}")
        return json.loads(t)

    def post(self, path: str, body: dict) -> tuple[int, str]:
        for _ in range(4):
            s, t = _req("POST", f"{self.base}/api{path}", self.h, body)
            if s == 429:
                time.sleep(6)
                continue
            return s, t
        return s, t

    def _create(self, kind: str, payload: dict) -> tuple[int, str]:
        s, t = self.post("/journal", {"kind": kind, "payload": payload})
        time.sleep(WRITE_PACING_S)
        return s, t

    def _apply(self, entry_id: str) -> tuple[int, str]:
        s, t = self.post(f"/journal/{entry_id}/apply", {})
        time.sleep(WRITE_PACING_S)
        return s, t

    def _reject(self, entry_id: str, reason: str) -> None:
        self.post(f"/journal/{entry_id}/reject", {"reason": reason})
        time.sleep(WRITE_PACING_S)

    # --- expectation helpers ---
    def ok(self, kind: str, payload: dict, label: str) -> bool:
        """Expect create AND apply to succeed."""
        s, t = self._create(kind, payload)
        if s != 200:
            log.append(("FAIL", label, f"create {kind} -> {s}: {t}"))
            return False
        eid = json.loads(t)["id"]
        s, t = self._apply(eid)
        if s != 200:
            log.append(("FAIL", label, f"apply {kind} -> {s}: {t}"))
            return False
        log.append(("OK", label, kind))
        return True

    def reject_at_create(self, kind: str, payload: dict, label: str, why: str) -> None:
        """Expect the create to be rejected with 400. If accepted -> suspect bug."""
        s, t = self._create(kind, payload)
        if s == 400:
            log.append(("GOOD_REJECT", label, f"{kind} correctamente rechazado en create"))
            return
        if s != 200:
            log.append(("GOOD_REJECT", label, f"{kind} rechazado en create ({s})"))
            return
        # Accepted at create — try apply to see if it also slips through.
        eid = json.loads(t)["id"]
        sa, ta = self._apply(eid)
        if sa == 200:
            log.append(("SUSPECT", label, f"{kind} ACEPTADO pese a: {why} (create 200 + apply 200)"))
            findings.append(f"{label}: {kind} aceptado y aplicado pese a que {why}. Payload: {json.dumps(payload, ensure_ascii=False)}")
        else:
            log.append(("SUSPECT", label, f"{kind} pasó el create (200) y falló en apply ({sa}: {ta.strip()[:120]}) — debería rechazarse en create. Motivo: {why}"))
            findings.append(f"{label}: {kind} se acepta en create (200) y solo falla en apply con '{ta.strip()[:120]}'. Validación tardía. Motivo esperado de rechazo: {why}")
            self._reject(eid, "exercise: limpieza de entrada que debió rechazarse en create")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    args = ap.parse_args()
    c = Client(args.base)
    try:
        me = c.get("/auth/me")
        print(f"Auth OK -> {me.get('username')}")
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 2

    skills = [s["id"] for s in c.get("/skills")]
    valid_skill = skills[0]

    # =====================================================================
    # PART A — FUNCTIONAL COVERAGE of the 14 kinds the seed didn't exercise
    # =====================================================================
    print("\n== A. Cobertura funcional de kinds restantes ==")

    # 1. person_update — enrich an existing person (reversible, harmless).
    c.ok("person_update", {"id": "elena_costa", "global_level": "intermediate",
                           "languages": ["pt", "en", "es"]}, "person_update:elena_costa")

    # 2. project_update — move a pipeline project's estimated hours / status round-trip.
    c.ok("project_update", {"code": "ACM-2026-002", "estimated_hours": 640}, "project_update:ACM-2026-002")

    # 3. client_update — refine a client's description.
    c.ok("client_update", {"id": "nimbus_health",
                           "description": "Telemedicina; pentest infra + revisión cloud (actualizado)."},
         "client_update:nimbus_health")

    # 4. contact_update — edit the first ACME contact (index 0).
    c.ok("contact_update", {"client_id": "acme_corp", "contact_index": 0,
                            "phone": "+34 600 999 000"}, "contact_update:acme_corp[0]")

    # 5. contact_add + 6. contact_remove — full add/remove cycle on a client.
    if c.ok("contact_add", {"client_id": "vortex_retail", "name": "Temp Contact",
                            "role": "Temporal", "email": "temp@vortex.example"},
            "contact_add:vortex_retail(temp)"):
        # remove the just-added contact (it's the last index)
        vortex = next(cl for cl in c.get("/clients") if cl["id"] == "vortex_retail")
        last_idx = len(vortex.get("contacts", [])) - 1
        c.ok("contact_remove", {"client_id": "vortex_retail", "contact_index": last_idx},
             "contact_remove:vortex_retail(temp)")

    # 7. office_create — new office.
    c.ok("office_create", {"office_id": "valencia", "city": "Valencia", "country": "ES",
                           "lat": 39.4699, "lon": -0.3763}, "office_create:valencia")
    # 8. office_update — adjust it.
    c.ok("office_update", {"office_id": "valencia", "country": "ES", "lat": 39.47},
         "office_update:valencia")
    # 9. office_archive — archive then unarchive (round-trip, keeps catalog clean).
    c.ok("office_archive", {"office_id": "valencia", "archived": True}, "office_archive:valencia")
    c.ok("office_archive", {"office_id": "valencia", "archived": False}, "office_unarchive:valencia")

    # 10. skill_label_update — relabel the seed's custom skill.
    c.ok("skill_label_update", {"skill_id": "purple_teaming",
                                "label_es": "Purple teaming",
                                "description": "Colaboración red/blue (etiqueta actualizada)."},
         "skill_label_update:purple_teaming")

    # 11. skill_catalog_create + 12. skill_catalog_archive — create a throwaway skill, archive it.
    if c.ok("skill_catalog_create", {"id": "zz_temp_skill", "label_es": "Skill temporal",
                                     "description": "Throwaway para ejercicio."},
            "skill_catalog_create:zz_temp_skill"):
        c.ok("skill_catalog_archive", {"id": "zz_temp_skill", "archived": True},
             "skill_catalog_archive:zz_temp_skill")

    # 13. assign + 14. unassign — full assignment lifecycle on a throwaway project.
    if c.ok("client_create", {"id": "zz_temp_client", "name": "ZZ Temp Client"},
            "client_create:zz_temp_client"):
        if c.ok("project_create", {"code": "ZZZ-2026-001", "client_alias": "zz_temp_client",
                                   "type": "internal", "window_start": "2026-09-01",
                                   "window_end": "2026-09-30", "status": "pipeline"},
                "project_create:ZZZ-2026-001"):
            c.ok("assign", {"person_id": "javier_soto", "project_code": "ZZZ-2026-001",
                            "dedication_pct": 25, "start": "2026-09-01", "end": "2026-09-30",
                            "role": "executor"}, "assign:javier->ZZZ")
            c.ok("unassign", {"person_id": "javier_soto", "project_code": "ZZZ-2026-001"},
                 "unassign:javier->ZZZ")
            # archive the throwaway project + client to keep active views clean
            c.ok("project_archive", {"code": "ZZZ-2026-001", "archived": True},
                 "project_archive:ZZZ-2026-001")
        c.ok("client_archive", {"id": "zz_temp_client", "archived": True},
             "client_archive:zz_temp_client")

    # person_archive — create a throwaway person, archive it (keeps the 10 seed people).
    if c.ok("person_create", {"id": "zz_temp_person", "full_name": "ZZ Temp",
                              "office": "remote", "start_date": "2026-01-01"},
            "person_create:zz_temp_person"):
        c.ok("person_archive", {"id": "zz_temp_person", "archived": True},
             "person_archive:zz_temp_person")

    # =====================================================================
    # PART B — EDGE CASES / BUG HUNTING (should be rejected at create)
    # =====================================================================
    print("== B. Casos límite / caza de bugs ==")

    # Duplicates
    c.reject_at_create("person_create", {"id": "ana_torres", "full_name": "Dup",
                                         "office": "madrid", "start_date": "2026-01-01"},
                       "dup:person", "ya existe una persona con ese id")
    c.reject_at_create("client_create", {"id": "acme_corp", "name": "Dup"},
                       "dup:client", "ya existe un cliente con ese id")
    c.reject_at_create("project_create", {"code": "ACM-2026-001", "client_alias": "acme_corp",
                                          "type": "pentest_web", "window_start": "2026-02-01",
                                          "window_end": "2026-03-15"},
                       "dup:project", "ya existe un proyecto con ese code")
    c.reject_at_create("office_create", {"office_id": "madrid", "city": "Madrid"},
                       "dup:office", "ya existe una oficina con ese id")
    c.reject_at_create("skill_catalog_create", {"id": valid_skill, "label_es": "Dup"},
                       "dup:skill", "ya existe una skill con ese id")

    # Dangling references
    c.reject_at_create("assign", {"person_id": "ghost", "project_code": "ACM-2026-001",
                                  "dedication_pct": 10, "start": "2026-02-01", "end": "2026-02-10"},
                       "ref:assign-person", "la persona no existe")
    c.reject_at_create("assign", {"person_id": "ana_torres", "project_code": "GHOST-9999-999",
                                  "dedication_pct": 10, "start": "2026-02-01", "end": "2026-02-10"},
                       "ref:assign-project", "el proyecto no existe")
    c.reject_at_create("person_update", {"id": "ghost", "city": "X"},
                       "ref:person_update", "la persona no existe")
    c.reject_at_create("unassign", {"person_id": "ana_torres", "project_code": "INT-2026-001"},
                       "ref:unassign-noactive", "no hay asignación activa que coincida")

    # Out-of-range contact index
    c.reject_at_create("contact_update", {"client_id": "acme_corp", "contact_index": 99, "name": "X"},
                       "range:contact_update", "el índice de contacto está fuera de rango")
    c.reject_at_create("contact_remove", {"client_id": "acme_corp", "contact_index": 99},
                       "range:contact_remove", "el índice de contacto está fuera de rango")

    # Duplicate active assignment (ana already on ACM-2026-001 from seed? check)
    # bruno_silva IS on ACM-2026-001 start 2026-02-01 -> exact triple duplicate
    c.reject_at_create("assign", {"person_id": "bruno_silva", "project_code": "ACM-2026-001",
                                  "dedication_pct": 50, "start": "2026-02-01", "end": "2026-03-15"},
                       "dup:assign-active", "ya existe una asignación activa con el mismo person/project/start")

    # Inverted date ranges (semantic; pydantic only checks date format, not order)
    c.reject_at_create("assign", {"person_id": "ana_torres", "project_code": "INT-2026-001",
                                  "dedication_pct": 10, "start": "2026-05-01", "end": "2026-04-01"},
                       "date:assign-inverted", "la fecha de fin es anterior a la de inicio")
    c.reject_at_create("availability", {"person_id": "ana_torres", "availability_kind": "pto",
                                        "start": "2026-05-10", "end": "2026-05-01"},
                       "date:avail-inverted", "la fecha de fin es anterior a la de inicio")
    c.reject_at_create("project_create", {"code": "ZZ-2026-777", "client_alias": "acme_corp",
                                          "type": "pentest_web", "window_start": "2026-06-01",
                                          "window_end": "2026-05-01"},
                       "date:project-inverted", "la ventana termina antes de empezar")

    # Out-of-bounds numerics (pydantic constraints should catch at create)
    c.reject_at_create("assign", {"person_id": "ana_torres", "project_code": "INT-2026-001",
                                  "dedication_pct": 999, "start": "2026-06-01", "end": "2026-06-10"},
                       "num:assign-pct", "dedication_pct supera el máximo (200)")
    c.reject_at_create("skill_update", {"person_id": "ana_torres", "skill_id": valid_skill, "level": 9},
                       "num:skill-level", "el nivel supera el máximo (5)")
    c.reject_at_create("availability", {"person_id": "ana_torres", "availability_kind": "pto",
                                        "start": "2026-06-01", "end": "2026-06-10", "pct": 150},
                       "num:avail-pct", "pct supera el máximo (100)")

    # Bad enums
    c.reject_at_create("availability", {"person_id": "ana_torres", "availability_kind": "vacaciones",
                                        "start": "2026-06-01", "end": "2026-06-10"},
                       "enum:avail-kind", "availability_kind no es un valor válido")
    c.reject_at_create("assign", {"person_id": "ana_torres", "project_code": "INT-2026-001",
                                  "dedication_pct": 10, "start": "2026-06-01", "end": "2026-06-10",
                                  "role": "jefe"},
                       "enum:assign-role", "role no es un valor válido")

    # Reference an archived project in a new assignment
    c.reject_at_create("assign", {"person_id": "ana_torres", "project_code": "ZZZ-2026-001",
                                  "dedication_pct": 10, "start": "2026-10-01", "end": "2026-10-10"},
                       "ref:assign-archived-project", "el proyecto está archivado")

    # ----- Summary -----
    cats = {}
    for cat, _, _ in log:
        cats[cat] = cats.get(cat, 0) + 1
    print("\n" + "=" * 64)
    print("EXERCISE SUMMARY")
    for cat in ("OK", "GOOD_REJECT", "SUSPECT", "FAIL"):
        if cats.get(cat):
            print(f"  {cat}: {cats[cat]}")
    fails = [x for x in log if x[0] == "FAIL"]
    if fails:
        print("\nFAILS (operación funcional que no debió fallar):")
        for _, label, detail in fails:
            print(f"  [FAIL] {label}: {detail}")
    if findings:
        print("\nHALLAZGOS SOSPECHOSOS (posibles bugs):")
        for f in findings:
            print(f"  [!] {f}")
    else:
        print("\nSin hallazgos sospechosos: todos los casos límite se rechazaron correctamente.")
    print("=" * 64)
    return 1 if (fails or findings) else 0


if __name__ == "__main__":
    sys.exit(main())
