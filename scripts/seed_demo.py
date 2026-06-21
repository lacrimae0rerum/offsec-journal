#!/usr/bin/env python3
"""Populate an OffSec Journal dev instance with a realistic, permanent dataset.

Exercises every journal kind plus notes through the real HTTP API (exactly the
path the SPA uses), so any endpoint/validation/coherence bug surfaces here. Each
operation is logged OK/FAIL with the exact server error. Data is NOT archived at
the end -- the instance stays fully populated.

Pre-requisite: dev server on 127.0.0.1:8001 with DEV_USER=fer (Authelia bypass).

Usage:
    python3 scripts/seed_demo.py
    python3 scripts/seed_demo.py --base http://127.0.0.1:8001
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# 60 writes/min limiter on the server -> pace just under 1/sec to avoid 429.
WRITE_PACING_S = 1.05

results: list[tuple[str, bool, str]] = []  # (label, ok, detail)


def _request(method: str, url: str, headers: dict, body: dict | None) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class Client:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.headers = {"Remote-User": "fer", "Content-Type": "application/json"}

    def get(self, path: str):
        status, text = _request("GET", f"{self.base}/api{path}", self.headers, None)
        if status != 200:
            raise RuntimeError(f"GET {path} -> {status}: {text}")
        return json.loads(text)

    def _post(self, path: str, body: dict) -> tuple[int, str]:
        # Retry once on 429 honouring Retry-After.
        for attempt in range(4):
            status, text = _request("POST", f"{self.base}/api{path}", self.headers, body)
            if status == 429:
                wait = 5
                try:
                    wait = int(json.loads(text).get("detail", "").split("~")[1].split("s")[0])
                except Exception:
                    pass
                time.sleep(wait + 1)
                continue
            return status, text
        return status, text

    def journal(self, kind: str, payload: dict, label: str) -> bool:
        """Create a pending entry and apply it. Logs the outcome."""
        status, text = self._post("/journal", {"kind": kind, "payload": payload})
        if status != 200:
            results.append((label, False, f"create {kind} -> {status}: {text}"))
            return False
        time.sleep(WRITE_PACING_S)
        entry_id = json.loads(text)["id"]
        status, text = self._post(f"/journal/{entry_id}/apply", {})
        if status != 200:
            results.append((label, False, f"apply {kind} -> {status}: {text}"))
            return False
        time.sleep(WRITE_PACING_S)
        results.append((label, True, kind))
        return True

    def note(self, entity_type: str, entity_id: str, body: str, label: str, tags=None) -> bool:
        status, text = self._post("/notes", {
            "entity_type": entity_type, "entity_id": entity_id,
            "body": body, "tags": tags or [],
        })
        ok = status == 200
        results.append((label, ok, "note" if ok else f"{status}: {text}"))
        if ok:
            time.sleep(WRITE_PACING_S)
        return ok


# ---------------------------------------------------------------------------
# Dataset -- a plausible offensive-security team across Madrid/Barcelona/Lisboa.
# ---------------------------------------------------------------------------
CLIENTS = [
    {"id": "acme_corp", "name": "ACME Corporation", "sector": "Banca", "size": "large", "country": "ES",
     "description": "Banca minorista, pentests recurrentes sobre banca online y APIs."},
    {"id": "nimbus_health", "name": "Nimbus Health", "sector": "Salud", "size": "mid", "country": "PT",
     "description": "Plataforma de telemedicina; cumplimiento y revision de infraestructura."},
    {"id": "vortex_retail", "name": "Vortex Retail", "sector": "Retail", "size": "large", "country": "ES",
     "description": "E-commerce y cloud; foco en aplicaciones web y contenedores."},
    {"id": "zenith_gov", "name": "Zenith Public Sector", "sector": "Sector publico", "size": "large", "country": "ES",
     "description": "Organismo publico; red team y campanas de phishing autorizadas."},
]

CONTACTS = [
    {"client_id": "acme_corp", "name": "Marta Gil", "role": "CISO", "email": "marta.gil@acme.example", "phone": "+34 600 111 222"},
    {"client_id": "acme_corp", "name": "Pablo Vidal", "role": "SecOps Lead", "email": "pablo.vidal@acme.example", "phone": ""},
    {"client_id": "nimbus_health", "name": "Rui Santos", "role": "CTO", "email": "rui.santos@nimbus.example", "phone": "+351 910 000 111"},
    {"client_id": "vortex_retail", "name": "Laura Pena", "role": "Head of IT", "email": "laura.pena@vortex.example", "phone": ""},
    {"client_id": "zenith_gov", "name": "Carlos Ferro", "role": "Responsable de Seguridad", "email": "carlos.ferro@zenith.example", "phone": ""},
]

# office must reference an existing office_id: madrid|barcelona|lisboa|remote
PEOPLE = [
    {"id": "ana_torres", "full_name": "Ana Torres", "office": "madrid", "city": "Madrid", "timezone": "CET",
     "languages": ["es", "en"], "base_role": "team_lead", "global_level": "master", "contractual_fte": 1.0, "start_date": "2021-03-01"},
    {"id": "bruno_silva", "full_name": "Bruno Silva", "office": "lisboa", "city": "Lisboa", "timezone": "WET",
     "languages": ["pt", "en"], "base_role": "pentester", "global_level": "senior", "contractual_fte": 1.0, "start_date": "2022-01-15"},
    {"id": "carla_mendez", "full_name": "Carla Mendez", "office": "barcelona", "city": "Barcelona", "timezone": "CET",
     "languages": ["es", "ca", "en"], "base_role": "pentester", "global_level": "senior", "contractual_fte": 0.8, "start_date": "2022-06-01"},
    {"id": "diego_ramos", "full_name": "Diego Ramos", "office": "madrid", "city": "Madrid", "timezone": "CET",
     "languages": ["es", "en"], "base_role": "red_teamer", "global_level": "master", "contractual_fte": 1.0, "start_date": "2020-09-10"},
    {"id": "elena_costa", "full_name": "Elena Costa", "office": "lisboa", "city": "Lisboa", "timezone": "WET",
     "languages": ["pt", "en"], "base_role": "pentester", "global_level": "junior", "contractual_fte": 1.0, "start_date": "2024-09-02"},
    {"id": "fernando_ruiz", "full_name": "Fernando Ruiz", "office": "remote", "city": "Valencia", "timezone": "CET",
     "languages": ["es", "en"], "base_role": "pentester", "global_level": "intermediate", "contractual_fte": 0.5, "start_date": "2023-04-20"},
    {"id": "gabriela_nunes", "full_name": "Gabriela Nunes", "office": "barcelona", "city": "Barcelona", "timezone": "CET",
     "languages": ["pt", "es", "en"], "base_role": "pentester", "global_level": "junior", "contractual_fte": 1.0, "start_date": "2025-01-13"},
    {"id": "hugo_marin", "full_name": "Hugo Marin", "office": "madrid", "city": "Madrid", "timezone": "CET",
     "languages": ["es", "en"], "base_role": "pentester", "global_level": "senior", "contractual_fte": 1.0, "start_date": "2021-11-08"},
    {"id": "ines_lopes", "full_name": "Ines Lopes", "office": "lisboa", "city": "Lisboa", "timezone": "WET",
     "languages": ["pt", "en", "fr"], "base_role": "pentester", "global_level": "intermediate", "contractual_fte": 1.0, "start_date": "2023-02-27"},
    {"id": "javier_soto", "full_name": "Javier Soto", "office": "remote", "city": "Sevilla", "timezone": "CET",
     "languages": ["es"], "base_role": "pentester", "global_level": "junior", "contractual_fte": 0.8, "start_date": "2025-03-03"},
]

# person_id -> [(skill_id, level, growth_interest)]
SKILLS = {
    "ana_torres": [("reporting", 5, False), ("hacking_active_directory", 5, False), ("pivoting_movimiento_lateral", 4, False),
                   ("ingenieria_social", 4, True), ("hacking_cloud", 3, True)],
    "bruno_silva": [("hacking_web", 5, False), ("explotacion_logica_negocio", 4, False), ("bypass_autenticacion", 4, False),
                    ("reporting", 3, True), ("hacking_cloud", 2, True)],
    "carla_mendez": [("explotacion_servicios_red", 5, False), ("pivoting_movimiento_lateral", 4, False),
                     ("escalada_privilegios", 4, False), ("hacking_active_directory", 3, True),
                     ("evasion_controles_red", 3, False)],
    "diego_ramos": [("evasion_defensas", 5, False), ("desarrollo_exploits", 5, False), ("evasion_controles_red", 4, False),
                    ("acceso_fisico", 3, True), ("phishing", 4, False), ("ingenieria_social", 4, False)],
    "elena_costa": [("hacking_web", 2, True), ("osint", 3, True), ("reconocimiento_externo", 2, True)],
    "fernando_ruiz": [("hacking_contenedores", 4, False), ("hacking_cloud", 4, True),
                      ("automatizacion_tooling", 3, False), ("hacking_web", 3, False)],
    "gabriela_nunes": [("osint", 3, True), ("phishing", 2, True), ("reconocimiento_externo", 3, True)],
    "hugo_marin": [("hacking_active_directory", 4, False), ("escalada_privilegios", 5, False),
                   ("pivoting_movimiento_lateral", 4, False), ("explotacion_servicios_red", 4, True),
                   ("hacking_contenedores", 3, False)],
    "ines_lopes": [("hacking_web", 3, False), ("bypass_autenticacion", 3, True),
                   ("explotacion_logica_negocio", 3, False), ("reporting", 3, True)],
    "javier_soto": [("reconocimiento_externo", 2, True), ("osint", 2, True), ("automatizacion_tooling", 2, True)],
}

PROJECTS = [
    {"code": "ACM-2026-001", "client_alias": "acme_corp", "type": "pentest_web", "window_start": "2026-02-01",
     "window_end": "2026-03-15", "estimated_hours": 320, "status": "active",
     "required_skills": [{"skill_id": "hacking_web", "weight": 3, "min_level": 4},
                         {"skill_id": "bypass_autenticacion", "weight": 2, "min_level": 3},
                         {"skill_id": "reporting", "weight": 1, "min_level": 3}]},
    {"code": "ACM-2026-002", "client_alias": "acme_corp", "type": "red_team", "window_start": "2026-04-01",
     "window_end": "2026-06-30", "estimated_hours": 600, "status": "pipeline",
     "required_skills": [{"skill_id": "evasion_defensas", "weight": 3, "min_level": 4},
                         {"skill_id": "hacking_active_directory", "weight": 3, "min_level": 4},
                         {"skill_id": "ingenieria_social", "weight": 2, "min_level": 3}]},
    {"code": "NMB-2026-001", "client_alias": "nimbus_health", "type": "pentest_infra", "window_start": "2026-02-10",
     "window_end": "2026-03-20", "estimated_hours": 280, "status": "active",
     "required_skills": [{"skill_id": "explotacion_servicios_red", "weight": 3, "min_level": 4},
                         {"skill_id": "escalada_privilegios", "weight": 2, "min_level": 4},
                         {"skill_id": "pivoting_movimiento_lateral", "weight": 2, "min_level": 3}]},
    {"code": "VTX-2026-001", "client_alias": "vortex_retail", "type": "pentest_web", "window_start": "2026-03-01",
     "window_end": "2026-04-10", "estimated_hours": 360, "status": "active",
     "required_skills": [{"skill_id": "hacking_web", "weight": 3, "min_level": 3},
                         {"skill_id": "hacking_contenedores", "weight": 2, "min_level": 4},
                         {"skill_id": "hacking_cloud", "weight": 2, "min_level": 4}]},
    {"code": "ZEN-2026-001", "client_alias": "zenith_gov", "type": "red_team", "window_start": "2026-05-01",
     "window_end": "2026-07-31", "estimated_hours": 520, "status": "pipeline",
     "required_skills": [{"skill_id": "phishing", "weight": 3, "min_level": 4},
                         {"skill_id": "ingenieria_social", "weight": 3, "min_level": 4},
                         {"skill_id": "osint", "weight": 2, "min_level": 3}]},
    {"code": "INT-2026-001", "client_alias": "acme_corp", "type": "internal", "window_start": "2026-01-15",
     "window_end": "2026-12-31", "estimated_hours": 200, "status": "active",
     "required_skills": [{"skill_id": "automatizacion_tooling", "weight": 2, "min_level": 3}]},
]

# (person, project, dedication_pct, start, end, role)
ASSIGNMENTS = [
    ("bruno_silva", "ACM-2026-001", 70, "2026-02-01", "2026-03-15", "lead"),
    ("ines_lopes", "ACM-2026-001", 50, "2026-02-01", "2026-03-15", "executor"),
    ("ana_torres", "ACM-2026-001", 20, "2026-02-01", "2026-03-15", "reviewer"),
    ("elena_costa", "ACM-2026-001", 40, "2026-02-10", "2026-03-15", "shadow"),
    ("diego_ramos", "ACM-2026-002", 60, "2026-04-01", "2026-06-30", "lead"),
    ("ana_torres", "ACM-2026-002", 30, "2026-04-01", "2026-06-30", "reviewer"),
    ("carla_mendez", "NMB-2026-001", 80, "2026-02-10", "2026-03-20", "lead"),
    ("hugo_marin", "NMB-2026-001", 60, "2026-02-10", "2026-03-20", "executor"),
    ("fernando_ruiz", "VTX-2026-001", 50, "2026-03-01", "2026-04-10", "lead"),
    ("gabriela_nunes", "VTX-2026-001", 60, "2026-03-01", "2026-04-10", "executor"),
    ("diego_ramos", "ZEN-2026-001", 50, "2026-05-01", "2026-07-31", "lead"),
    ("javier_soto", "INT-2026-001", 30, "2026-01-15", "2026-12-31", "executor"),
    # Deliberate over-allocation: hugo already at 60% on NMB, add 70% overlapping
    # -> should surface as a coherence warning (>100% in the same window).
    ("hugo_marin", "VTX-2026-001", 70, "2026-03-01", "2026-03-20", "executor"),
]

# (person, kind, start, end, pct, reason)
AVAILABILITY = [
    ("ana_torres", "pto", "2026-03-16", "2026-03-27", 100, "Vacaciones"),
    ("bruno_silva", "training", "2026-02-23", "2026-02-25", 100, "Curso OSCP"),
    ("carla_mendez", "pto", "2026-04-06", "2026-04-10", 100, "Semana Santa"),
    ("elena_costa", "sick", "2026-02-16", "2026-02-18", 100, "Baja medica"),
    ("fernando_ruiz", "overhead", "2026-01-01", "2026-12-31", 20, "Soporte interno"),
    ("diego_ramos", "hold", "2026-08-01", "2026-08-21", 100, "Reserva pendiente de confirmar"),
]

NOTES = [
    ("person", "diego_ramos", "Referente de red team; mentor de juniors en evasion.", ["mentor"]),
    ("person", "elena_costa", "Onboarding en curso; emparejada con Bruno en ACME web.", ["onboarding"]),
    ("project", "ACM-2026-001", "Alcance: banca online + 3 APIs. Ventana confirmada por el cliente.", ["scope"]),
    ("client", "acme_corp", "Cliente recurrente desde 2021; SLA de reporte de 5 dias habiles.", ["sla"]),
]

# New skill to exercise the catalog-create kind.
NEW_SKILLS = [
    {"id": "purple_teaming", "label_es": "Purple teaming", "description": "Colaboracion red/blue para mejorar deteccion."},
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    args = ap.parse_args()
    c = Client(args.base)

    # Sanity: server reachable + auth works.
    try:
        me = c.get("/auth/me")
        print(f"Auth OK -> user={me.get('username')} team={me.get('team_id')}")
    except Exception as e:
        print(f"FATAL: server not reachable / auth failed: {e}", file=sys.stderr)
        return 2

    print("\n== Phase 0: skill catalog ==")
    for s in NEW_SKILLS:
        c.journal("skill_catalog_create", s, f"skill:{s['id']}")

    print("== Phase 1: clients ==")
    for cl in CLIENTS:
        c.journal("client_create", cl, f"client:{cl['id']}")

    print("== Phase 2: contacts ==")
    for ct in CONTACTS:
        c.journal("contact_add", ct, f"contact:{ct['client_id']}:{ct['name']}")

    print("== Phase 3: people ==")
    for p in PEOPLE:
        c.journal("person_create", p, f"person:{p['id']}")

    print("== Phase 4: skills ==")
    for pid, skills in SKILLS.items():
        for sid, level, growth in skills:
            c.journal("skill_update",
                      {"person_id": pid, "skill_id": sid, "level": level, "growth_interest": growth},
                      f"skill_update:{pid}:{sid}")

    print("== Phase 5: projects ==")
    for pr in PROJECTS:
        c.journal("project_create", pr, f"project:{pr['code']}")

    print("== Phase 6: assignments ==")
    for pid, code, pct, start, end, role in ASSIGNMENTS:
        c.journal("assign",
                  {"person_id": pid, "project_code": code, "dedication_pct": pct,
                   "start": start, "end": end, "role": role},
                  f"assign:{pid}->{code}")

    print("== Phase 7: availability ==")
    for pid, kind, start, end, pct, reason in AVAILABILITY:
        c.journal("availability",
                  {"person_id": pid, "availability_kind": kind, "start": start,
                   "end": end, "pct": pct, "reason": reason},
                  f"avail:{pid}:{kind}")

    print("== Phase 8: notes ==")
    for et, eid, body, tags in NOTES:
        c.note(et, eid, body, f"note:{et}:{eid}", tags)

    # ----- Coherence / derived-view checks (read-only) -----
    print("\n== Phase 9: derived views ==")
    derived_errors = []
    try:
        coh = c.get("/coherence")
        n = len(coh) if isinstance(coh, list) else len(coh.get("warnings", []))
        print(f"coherence warnings: {n}")
        if isinstance(coh, list):
            for w in coh[:10]:
                print(f"  - {json.dumps(w, ensure_ascii=False)[:160]}")
    except Exception as e:
        derived_errors.append(f"coherence: {e}")
    for path, label in [("/skill-gap?scope=active", "skill-gap"),
                        ("/heatmap?start=2026-02-01&end=2026-04-30", "heatmap"),
                        ("/geo", "geo"), ("/search?q=ana", "search")]:
        try:
            c.get(path)
            print(f"{label}: OK")
        except Exception as e:
            derived_errors.append(f"{label}: {e}")

    # ----- Summary -----
    ok = [r for r in results if r[1]]
    fail = [r for r in results if not r[1]]
    print("\n" + "=" * 60)
    print(f"SEED SUMMARY: {len(ok)} ok, {len(fail)} failed, {len(results)} total")
    if fail:
        print("\nFAILED OPERATIONS (potential bugs):")
        for label, _, detail in fail:
            print(f"  [FAIL] {label}\n         {detail}")
    if derived_errors:
        print("\nDERIVED-VIEW ERRORS:")
        for e in derived_errors:
            print(f"  [ERR] {e}")
    print("=" * 60)
    return 1 if (fail or derived_errors) else 0


if __name__ == "__main__":
    sys.exit(main())
