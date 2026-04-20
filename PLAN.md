# PLAN.md — estado y roadmap

Última revisión: 2026-04-19.

## Estado actual

### ✅ Completado

**Frontend estático (12 páginas + 9 modales CRUD)**

Modales construidos y conectados:
- `reject-modal` — rechazar entry del journal con reason obligatoria
- `new-project-modal` — crear proyecto (`project_create`)
- `new-avail-modal` — crear PTO/training (`availability`)
- `new-person-modal` — crear persona (`person_create`)
- `new-client-modal` — crear cliente (`client_create`)
- `propose-assign-modal` — proponer assignment (`assign`)
- `archive-modal` — archivar person/project/client/office (genérico)
- `contact-modal` — add/edit/remove contacto (`contact_add`/`contact_update`/`contact_remove`)
- `skill-modal` — añadir o editar skill de persona (`skill_update`)

Botones de archivado en person-detail y project-detail; click en skill-row abre edit; click en contact abre edit; "+ Contacto" y "+ Nuevo cliente" accesibles desde Clients.

- Overview (KPIs, heatmap 1S–6M con altura de celda uniforme, top gaps, coherence warnings, journal reciente)
- People (filtros + tabla + drawer con radar SVG)
- Person detail (`/people/:id` — radar, skills detalle, assignments, coherence, availability, notas)
- Projects (kanban / tabla toggle + modal nuevo proyecto)
- Project detail (`/projects/:code` — required skills vs equipo, timeline, notas)
- Clients (master-detail con proyectos, contactos, placeholders, notas)
- Schedule (heatmap persona × semana con popover breakdown, hover/click tweak)
- Skills (matriz niveles ↔ gap bars)
- Map (grid map con markers + popover)
- Journal (pending/applied/rejected tabs, apply/reject, modal con reason)
- Chat (split layout con 3 flows mockeados + tool calls panel)
- Search (facets + grouped results + match highlight)
- Modales: nuevo proyecto, nueva availability, nueva persona, reject con reason
- Tweaks panel (sidebar full/mini, schedule hover/click)

**Backend FastAPI**
- Estructura del paquete `api/` (config, auth, main, models, core, routes)
- 8 modelos pydantic v2 con `archived:bool` (Person, PersonSkill, Project, RequiredSkill, Assignment, Availability, Skill, Office, Client, Contact, JournalEntry + 20 payloads tipados, Note)
- SQLite schema idempotente con FTS5 para notas (`api/core/db.py`)
- ruamel YAML round-trip con backup/restore (`api/core/yaml_io.py`)
- `sync.py` — YAML → SQLite, `--confirm` para diffs destructivos
- Coherence rules (junior/intermediate/senior/master + insufficient_skill_coverage override)
- Journal apply/reject/create con 20 handlers tipados y rollback via `.bak`
- `last_used_on_project` auto-update en apply de `assign`
- Queries: list/get por entidad, skill_gap, heatmap (ISO week bounds), search FTS5
- Notes append-only (markdown con separador `--- ts | author | tags ---`)
- 20 endpoints read + write (journal, notes)
- X-API-Key auth middleware
- CORS, loguru rotación

**Seed + tests**
- 8 archivos YAML seed (skills 20, offices 4, people 6, projects 8, assignments 11+, availability 2, clients 8, journal 3+)
- 2 archivos markdown de ejemplo (`fer.md`, `PT-2026-018.md`)
- **90 tests verde** en 37 s:
  - 7 coherence (todas las reglas + override)
  - 3 sync (idempotencia, counts, skills embebidas)
  - 5 journal apply básicos (create, last_used, double-apply, reject, archive)
  - **24 handlers** — uno por cada uno de los 22 journal kinds + 2 edge cases (incluye `skill_catalog_create/archive`)
  - **34 endpoints** — FastAPI TestClient contra los 20 endpoints + auth + errores
  - 6 notes + FTS5 (append-only, round-trip, tokenizer sin diacríticos)
  - 7 heatmap (ISO weeks, year boundary, archived excluido, over-allocation)
  - **7 rollback** — `.bak` restore en fallos de payload (garantía de atomicidad)
- Sync corre en 128 ms sobre seed completo

**Wire-up parcial (frontend ↔ backend)**
- `web/api.js` — wrapper fetch con `X-API-Key` + 20 métodos tipados
- Tweaks panel: API Base URL + API Key con persistencia en localStorage
- Badge de estado online/offline/error (top-right)
- **Journal page conectada live**: list + apply + reject funcionan contra `/api/journal`
- End-to-end verificado: crear entry → apply → YAML mutado + sync + SQLite refrescado
- Resto de páginas siguen leyendo `DATA.*` (pendiente migración mecánica)

**Config**
- `pyproject.toml` (deps + dev deps + scripts + pytest)
- `Makefile` (install, up, sync, test, doctor, reset, web)
- `.env.example` + `.gitignore`

---

### ⏳ Pendiente

#### Prioridad 1 — Wire-up al backend

- [x] **Frontend fetch layer** (`web/api.js`): wrapper con `X-API-Key`, persistencia en localStorage, 20 métodos tipados, **4 normalizers** (person/project/client/journal)
- [x] **Settings UI**: API Base URL + API Key en el panel Tweaks con botón "Guardar + probar"
- [x] **Status badge**: online/offline/error en la esquina superior derecha
- [x] **Journal page**: list + apply + reject conectados live a `/api/journal`
- [x] **Modales**: `POST /api/journal` cuando online + refresh automático tras éxito
- [x] **refreshAll() + renderAll()**: Promise.all de 8 endpoints + muta DATA en sitio + re-render global
- [x] **Overview**: `/api/skill-gap` + `/api/coherence` + `/api/heatmap` + journal live
- [x] **People**: `/api/people` con load agregado y warning merged desde coherence
- [x] **Person Detail + drawer**: data live via DATA mutado
- [x] **Projects + Project Detail**: `/api/projects` con coverage computado cliente-side
- [x] **Clients + Client Detail**: `/api/clients` con contacts y projects embebidos
- [x] **Schedule**: `/api/heatmap` con rango elegible por week input
- [x] **Skills**: columnas dinámicas desde `/api/skills` (catálogo live), filas desde people.skills
- [x] **Map**: `/api/geo` actualiza los 3 markers con personas reales
- [x] **Search**: `/api/search?q=...` con debounce 220ms + highlight de matches
- [x] **Re-fetch after apply**: tras apply/reject/submit, `refreshAll()` pulla todo y re-renderiza
- [x] **Note append**: `refreshNotes()` + `submitNote()` en Person / Project / Client detail; tags CSV en input propio; XSS-safe con `_escapeHtml`
- [x] **Fix parser notas**: regex de separador corregida para aceptar tags con guiones (BUG-007) + test de regresión

#### Prioridad 2 — LLM chat streaming

- [ ] `agent/tools.py` — 10 tools: `find_people`, `get_person`, `get_project`, `who_is_free`, `skill_gap`, `propose_assignment`, `propose_availability`, `propose_skill_update`, `add_note`, `list_pending_journal`.
- [ ] `agent/prompts/system.md` — system prompt español, deja explícito que NO muta directamente.
- [ ] `api/routes/chat.py` — `POST /api/chat` SSE streaming, tool-loop server-side (max 5 iter), eventos tipados (`token`, `tool_call`, `tool_result`, `done`, `error`).
- [ ] `httpx` client directo a `http://localhost:11434/api/chat` (sin ollama-python).
- [ ] Frontend Chat: reemplazar demo estático por cliente SSE real.

#### Prioridad 3 — CLI y ops

- [ ] `cli.py` — entrypoint para `make doctor`, `sync --confirm`, `journal apply/reject`, `notes add`.
- [ ] `api/doctor.py` — verifica Ollama reachable, puertos libres, YAML válidos, DB writable.
- [ ] Port-conflict resolver en `make up` — si 3000/8000 ocupados, subir a 3001/8001 + banner + persist en `.env.local`.

#### Prioridad 4 — Infra y despliegue

- [ ] `Dockerfile.api` (Python 3.11-slim, venv, uvicorn)
- [ ] `Dockerfile.web` (nginx sirviendo `web/` estático)
- [ ] `docker-compose.yml` — servicios `api` y `web`, volúmenes para `data/` y `notes/`
- [ ] README de despliegue en red local del MSSP

#### Prioridad 5 — Frontend real (Next.js)

Opcional si el prototipo estático cubre la necesidad. El prompt original lo pide, pero el estático ya es navegable end-to-end.

- [ ] Next.js 14 App Router + TypeScript + Tailwind
- [ ] shadcn/ui inlined en `web/components/ui/` (no CLI)
- [ ] TanStack Query para fetching + cache
- [ ] Zod schemas derivados de los pydantic (manual, V2 auto con datamodel-code-generator)
- [ ] Recharts para radar + heatmap reales
- [ ] MapLibre GL con OSM raster tiles
- [ ] SSE client para `/chat`
- [ ] 1 suite Vitest con casos concretos

#### Prioridad 6 — Pulido y UX gaps

- [x] Edición inline de skills en `/people/:id` (modal `skill-modal`, click en row)
- [x] Drawer de contacto en `/clients/:id` (modal `contact-modal`, add/edit/remove)
- [x] Archivar person/project/client (modal `archive-modal`)
- [x] Botón "+ Nuevo cliente" funcional (modal `new-client-modal`)
- [x] Botón "+ Proponer assignment" funcional (modal `propose-assign-modal`)
- [x] Tabla editable de required_skills en `/projects/:code` (modal `req-skills-modal`, editor inline)
- [x] Modal edit-project (status, ventana, horas) — journal `project_update`
- [x] Modal edit-client (sector, size, country, description) — journal `client_update`
- [x] Modal edit-person (full_name, office, level, FTE, idiomas, tz) — journal `person_update`
- [x] Modal edit-skill-label (icono ✎ en matrix header) — journal `skill_label_update`
- [x] **Diff payload automático** en los 3 edit modales — solo se envían campos modificados
- [x] Skill catalog: crear + archivar skills desde la UI (`skill_catalog_create` + `skill_catalog_archive`)
- [ ] Skill catalog: editar `label_es` + `description` inline (modal pendiente; journal kind `skill_label_update` ya existe)
- [ ] Office admin page (create/edit/archive) — journals `office_*`
- [ ] Desarchivar desde filtro "archived=true" (reenviar `*_archive` con `archived:false`)
- [ ] Heatmap responsive: resize listener que recompute `refH`
- [ ] Empty states coherentes en páginas sin datos

---

## Orden de implementación sugerido

1. **Wire frontend → backend** (semana 1). El frontend ya funciona con mocks; cambiar la capa de datos y conectar los modales deja la UI funcional de punta a punta.
2. **LLM streaming** (semana 2). Requiere Ollama instalado. El tool-loop server-side es la parte delicada.
3. **CLI + doctor + port-conflict** (día). Pulido operativo.
4. **Docker + compose** (día). Packaging.
5. **Next.js rewrite** (semana+). Solo si el estático no basta.
6. **Pulido y edge cases** (continuo).

---

## Decisiones tomadas (ver OPEN_QUESTIONS.md)

1. **Apply 2 clicks** para humanos (mismo flujo que LLM)
2. **Soft delete** (`archived: true`); hard delete jamás
3. **UI** editable para labels/descriptions del skill catalog
4. **Notas append-only** estricto
5. **Journal tipado** — solo 20 kinds del discriminator

## Deuda técnica consciente

- Tipos TypeScript en frontend se mantienen en paralelo manual con pydantic. V2: generación con `datamodel-code-generator` o OpenAPI.
- SQLite sin migraciones (se reconstruye desde YAML en cada sync). Funciona porque la DB es cache, no source.
- No hay paginación en endpoints `list_*`. Aceptable con 6 personas + 8 proyectos; revisar a >100.
- Search FTS5 solo indexa notas. Personas/proyectos usan `LIKE` — OK con volumen bajo; upgrade si el equipo crece.
- No hay rate limiting (red local, 2 usuarios confiables). Añadir si se expone fuera.
- `make install` escribe `.env` solo si no existe; rotar API_KEY requiere borrado manual.

## Verificación

```bash
make test                              # 15/15 verde
python -m api.core.sync                # 128 ms, 0 destructivos
python -c "from api.main import app"   # 20 rutas registradas
```
