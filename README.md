# Offensive Security Journal

Tool interna de gestión para el equipo ofensivo del MSSP. Corre en red local, accesible desde la máquina del líder y la del colaborador.

Visualiza y gestiona personas, skills, proyectos, dedicación, disponibilidad y notas. Incluye un LLM local para consultas y propuestas de cambios estructurales (pendiente de conectar — ver [PLAN.md](PLAN.md)).

---

## Stack

| Capa | Tecnología | Estado |
|---|---|---|
| Fuente de verdad | YAML en `data/` (ruamel round-trip) | ✅ |
| Read-cache | SQLite + FTS5 (stdlib) | ✅ |
| Backend | FastAPI + pydantic v2 + loguru | ✅ 20 endpoints |
| Tests | pytest + FastAPI TestClient | ✅ **90/90 verde** (37 s) |
| LLM | Llama 3.1 8B vía Ollama nativo | ⏳ pendiente |
| Frontend | HTML/CSS/JS estático (prototipo) | ✅ 12 páginas + 9 modales CRUD |
| Frontend ↔ backend | `web/api.js` + `refreshAll()` | ✅ **todas las páginas live** con fallback DATA offline |
| Frontend real | Next.js 14 + TS + shadcn/ui + Tailwind | ⏳ pendiente |
| Orquestación | Docker Compose (api + web) | ⏳ pendiente |
| Auth | X-API-Key, autogenerada en `make install` | ✅ |

## Patrón journal (cerrado)

Toda mutación estructural (personas, proyectos, assignments, availability, skills, clientes, contactos, oficinas) pasa por `data/journal.yaml` como entry `pending`. El humano la aplica o rechaza desde `/journal` (UI) o CLI. Apply crea `.bak` del YAML afectado, muta con ruamel, corre `sync`. Si ruamel falla, restaura el `.bak`.

**Notas** (markdown en `notes/`) son append-only directo, sin journal.

**LLM** nunca muta; solo propone entries `pending`.

## Quickstart

Prereqs: Python 3.11+, Ollama (para LLM; opcional en V1).

```bash
make install       # crea .env con API_KEY + deps + sync inicial
make up            # api + frontend en :8000 (todo-en-uno)
```

Abre http://localhost:8000/. Ya está. El frontend auto-obtiene la API key del endpoint `/api/bootstrap` (sólo accesible desde loopback); no hay paso manual de copiar la key.

Otros targets:
```bash
make test          # 97 tests
make sync          # reconstruye SQLite desde YAML
make reset         # wipe SQLite (.bak kept)
make web           # sirve sólo el frontend en :3000 (raro, para dev)
```

El `.env` generado en `make install` contiene la `API_KEY` (32 bytes url-safe). Para despliegues fuera de loopback deshabilita el endpoint `/api/bootstrap` editando `api/routes/bootstrap.py` y que el usuario la pegue manualmente en el panel ⚙.

## Layout

```
api/           Backend FastAPI
├── main.py             entrypoint (crea app + monta routers)
├── config.py           Settings (pydantic-settings, .env)
├── auth.py             X-API-Key dependency
├── models/             8 modelos pydantic v2 (Person, Project, Client, …)
├── core/
│   ├── db.py           SQLite schema + FTS5
│   ├── yaml_io.py      ruamel round-trip + backup/restore
│   ├── sync.py         YAML → SQLite (idempotente, --confirm destructivos)
│   ├── coherence.py    reglas global_level ↔ skills
│   ├── journal.py      apply/reject/create con .bak rollback + 20 handlers
│   ├── queries.py      reads + skill_gap + heatmap + FTS search
│   └── notes.py        append-only markdown
└── routes/             13 routers — ver README del directorio

data/          Fuente de verdad en YAML — 8 archivos
notes/         Markdown append-only (persons/, projects/, clients/)
web/           Frontend prototipo estático (12 páginas)
tests/         15 tests verde — coherence, sync idempotencia, journal apply
```

## Endpoints (actuales)

```
GET  /api/health
GET  /api/people                 /api/people/:id    /api/people/:id/skills    /api/people/:id/coherence
GET  /api/projects               /api/projects/:code
GET  /api/clients                /api/clients/:id
GET  /api/skills, /api/offices, /api/geo
GET  /api/coherence
GET  /api/heatmap?start=YYYY-MM-DD&end=YYYY-MM-DD
GET  /api/skill-gap?scope=pipeline|active
GET  /api/search?q=...

GET  /api/journal?status=pending|applied|rejected
POST /api/journal                  crea entry (proposer=human)
POST /api/journal/:id/apply        ejecuta handler, hace .bak, sync
POST /api/journal/:id/reject       body: {reason}   — reason obligatorio

GET  /api/notes?entity_type=…&entity_id=…
POST /api/notes                  append-only markdown
```

Todos los endpoints requieren `X-API-Key` salvo `/api/health`. Missing: `POST /api/chat` (SSE streaming LLM).

## Entidades editables

| Entidad | Crear | Editar | Archivar | Ruta journal | UI modal |
|---|---|---|---|---|---|
| Personas | ✓ | ✓ | soft | `person_create/update/archive` | ✅ create + edit + archive |
| Skills de persona (embebidas) | ✓ | ✓ | quitar via level 0 | `skill_update` | ✅ add + edit |
| Proyectos | ✓ | ✓ | soft | `project_create/update/archive` | ✅ create + edit + archive |
| Required skills (embebidas) | ✓ | ✓ | ✓ | `project_update` | ✅ editor inline (req-skills-modal) |
| Assignments | ✓ | via unassign + new | soft (unassign) | `assign` / `unassign` | ✅ propose |
| Availability (PTO/training/…) | ✓ | — | soft | `availability` | ✅ create |
| Clientes | ✓ | ✓ | soft | `client_create/update/archive` | ✅ create + edit + archive |
| Contactos (embebidos) | ✓ | ✓ | quitar | `contact_add/update/remove` | ✅ add + edit + remove |
| Oficinas | ✓ | ✓ | soft | `office_create/update/archive` | ⏳ admin page |
| Skills catalog (labels/description) | ✓ | ✓ label/desc | soft | `skill_catalog_create/archive/label_update` | ✅ create + edit + archive |
| Notas | ✓ append | ✗ (audit) | ✗ | direct (`POST /api/notes`) | ✅ textareas en detalle |

Los 22 kinds del journal están implementados y testeados (24 tests de handlers). El gap restante está en: admin page de oficinas (create/edit/archive); filtro de "archivados" con unarchive UX.

**Soft delete** (decisión #2): `archived: true` — nada se borra nunca del todo. Filtros por defecto excluyen archivados; `?archived=true` los incluye.

**Apply de humanos** (decisión #1): entries `human` siguen el mismo flujo que `llm` — crear pending + aplicar desde `/journal` (2 clicks). No hay auto-apply.

**Skill catalog** (decisión #3): labels y descripciones editables por UI (propuesta via `skill_label_update`). Crear/borrar skills del catálogo requiere cambio de código + migración.

**Notas** (decisión #4): append-only estricto. No hay edit ni delete.

**Journal manual** (decisión #5): solo kinds tipados del discriminator (20 operaciones). No hay `otras_ops` freeform.

## Diseño visual

Paleta azul accent: negro `#000` + azul `#1e9be0`. Ubuntu para UI, JetBrains Mono para IDs/códigos/niveles. Sketch aesthetic (dashed borders) — intencional, no bug.

Heatmaps con 7 tramos de color diferenciado (empty → 5 azules progresivos → ámbar near-capacity → rojo over-allocated). Ver `web/app.js:hmColor`.

## Verificación

```bash
make test                              # 97/97 verde en 49 s
python -m api.core.sync                # 128 ms, 0 destructivos
python -c "from api.main import app"   # 20 rutas registradas
```

Cobertura de tests:

| Suite | Tests | Cubre |
|---|---|---|
| `test_coherence.py` | 7 | Reglas junior/intermediate/senior/master + insufficient_skill_coverage |
| `test_sync.py` | 3 | Idempotencia, counts, skills embebidas |
| `test_journal_apply.py` | 5 | Assign flow + last_used auto-update + reject reason |
| `test_handlers_all.py` | 24 | Los 22 journal kinds + 2 edge cases (incluye skill_catalog_create/archive) |
| `test_endpoints.py` | 34 | FastAPI TestClient — 20 endpoints + auth + 400/404 |
| `test_notes_and_search.py` | 7 | Append-only + FTS5 round-trip + diacríticos + parser de tags con guiones (BUG-007) |
| `test_heatmap.py` | 7 | ISO weeks (year boundary), archived excluido, over-allocation |
| `test_rollback.py` | 7 | `.bak` rollback en fallos de payload |
| **Total** | **97** | |

## Referencias

- [PLAN.md](PLAN.md) — estado detallado + roadmap
- [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) — decisiones y preguntas abiertas
- [MANUAL_TESTS.md](MANUAL_TESTS.md) — checklist de 150 tests manuales para validar el estado actual
- [OffSec Journal Prompt.md](OffSec%20Journal%20Prompt.md) — spec original
- [web/README.md](web/README.md) — detalles del prototipo frontend
