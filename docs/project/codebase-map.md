# OffSec Journal — Mapa del codebase

> Generado por `/alfred-dev:map-codebase` el 2026-06-15.
> Actualizar cuando cambien entrypoints, stack o dominios.

---

## Propósito

Herramienta interna para gestionar equipos de seguridad ofensiva multi-tenant.
Dos tenants aislados (**OffSec** e **InfoSec**) con personas, proyectos, clientes,
asignaciones, disponibilidad y notas propias. Catálogo de skills compartido.

La fuente de verdad son ficheros YAML en `data/{team}/`; SQLite es caché de lectura
reconstruible. Toda mutación pasa por un *journal* (pending → apply/reject) con rollback.

---

## Stack y runtime

| Capa | Tecnología | Versión mínima |
|---|---|---|
| Runtime | Python | 3.11+ |
| Framework API | FastAPI + uvicorn | 0.115 / 0.32 |
| Validación | Pydantic v2 | 2.9 |
| Persistencia fuente | YAML (ruamel.yaml) | 0.18 |
| Persistencia caché | SQLite FTS5 (stdlib) | — |
| HTTP client | httpx | 0.27 |
| IDs | python-ulid | 3.0 |
| Logging | loguru | 0.7 |
| Frontend | HTML/CSS/JS estático | — |
| Auth | Authelia (delegada) + middleware propio | — |
| Tests | pytest + pytest-asyncio | 8.3 / 0.24 |
| Lint/format | ruff | — |

---

## Entrypoints y rutas críticas

| Entrypoint | Descripción |
|---|---|
| `api/main.py` | FastAPI app; monta routers, logging, static files |
| `offsec` CLI (`api/cli.py`) | CLI de gestión de usuarios/teams vía script instalado |
| `make up` | Dev local: uvicorn con `--reload --no-proxy-headers` |
| `docker compose up -d --build` | Dev con Docker; expone `127.0.0.1:8001` |
| `make test` | pytest sobre `tests/` |

**Ruta de autenticación crítica:**
`nginx → Authelia (forward-auth) → FastAPI`; la cabecera `Remote-User` es la única prueba de identidad. En dev, se usa `DEV_USER` en `.env` o `Remote-User` por curl.

---

## Módulos y dominios principales

### `api/`

```
api/
├── main.py          — app FastAPI, montaje de routers
├── config.py        — Settings (pydantic-settings), rutas ROOT/DATA
├── cli.py           — CLI offsec (teams list, users add…)
├── core/
│   ├── db.py        — SQLite FTS5: schema, init, queries base
│   ├── sync.py      — YAML → SQLite sync (fuente de verdad a caché)
│   ├── journal.py   — Motor del journal: 22 kinds, apply/reject, rollback
│   ├── queries.py   — Queries parametrizadas team-scoped
│   ├── coherence.py — Validación cross-entity
│   ├── notes.py     — CRUD notas sobre YAML
│   └── yaml_io.py   — I/O YAML con ruamel (preserva comentarios/formato)
├── models/          — Pydantic models: person, project, client, assignment,
│                      availability, office, skill, note, journal
├── routes/          — 15 routers FastAPI:
│   ├── people, projects, clients, skills, offices, geo
│   ├── heatmap, skill_gap, coherence, search
│   ├── journal, notes
│   ├── admin, auth, health
└── security/
    ├── authelia.py  — Middleware: lee Remote-User → user row → team/role
    ├── audit.py     — Audit log (9 eventos) en SQLite
    └── rate_limit.py— Rate limiter: 60 writes/min por tenant
```

### `web/`

Frontend SPA estático montado en `/`:

| Fichero | Responsabilidad |
|---|---|
| `index.html` | ~2800 líneas; 11 páginas (sections), 16 modals |
| `app.js` | Lógica UI, handlers, renders, enrutado hash |
| `api.js` | Wrappers fetch hacia `/api/*` |
| `data.js` | Capa de datos en memoria (`DATA.*`); schedule weeks |

**Páginas:** Dashboard, People, Projects, Clients, Offices, Skills, Heatmap,
Skill-Gap, Search, Chat (mock), Admin (sin UI todavía).

### `tests/`

14 módulos de tests de integración con FastAPI `TestClient`:

| Módulo | Cubre |
|---|---|
| `test_endpoints.py` | CRUD principal de todos los routers |
| `test_journal_apply.py` | Flujo apply/reject/rollback |
| `test_search_filters.py` | Filtros type/date/tags de search (D3) |
| `test_rate_limit_and_reactivation.py` | 429 en writes + reactivación de assignment |
| `test_team_isolation.py` | Aislamiento multi-tenant |
| `test_admin_endpoints.py` | `/api/admin/*` |
| `test_authelia_middleware.py` | Middleware Remote-User |
| `test_audit_regressions.py` | Audit log regresiones |
| `test_coherence.py` | Validación cross-entity |
| `test_heatmap.py` | Heatmap de carga |
| `test_rollback.py` | Rollback y backup |
| `test_sync.py` | YAML → SQLite sync |
| `test_notes_and_search.py` | Notes + FTS5 search básica |
| `test_cli.py` | CLI offsec |
| `test_handlers_all.py` | Handlers de todos los kinds |

**Total: 188 tests. Sin E2E browser (Playwright/Cypress: pendiente).**

---

## Build y despliegue

```bash
make install   # venv + pip install -e .[dev] + .env sample
make up        # uvicorn dev (--reload --no-proxy-headers) → :8000
make test      # pytest
docker compose up -d --build  # → :8001
```

- **Sin CI/CD configurado** (0%). `Makefile` + Docker son los únicos artefactos de build.
- Deploy en producción: pendiente nginx + Authelia + systemd (Nivel 3 del ROADMAP).

---

## Convenciones y patrones que respetar

1. **YAML es la fuente de verdad.** Nunca modificar SQLite directamente; siempre pasar por journal + sync.
2. **Journal-first para mutaciones.** Todo cambio va vía `POST /api/journal` (pending) y luego `apply`. No hay mutaciones directas en la mayoría de endpoints.
3. **Team-scoped en todo.** Cada query lleva el `team` del usuario autenticado. El tenant no puede filtrarse desde el request del usuario.
4. **Remote-User es el único canal de identidad.** No añadir auth propia; Authelia la gestiona.
5. **IDs con ULID.** No usar UUID ni secuencias autoincrementales.
6. **Errores nunca silenciosos.** `loguru` structured logging; no `except` genérico.
7. **Frontend: vanilla JS.** No introducir frameworks sin decisión explícita (D2: Next.js aplazado).
8. **ruff** para lint y formato en todo el código Python.

---

## Riesgos, deuda visible y preguntas abiertas

### Riesgos activos

| Riesgo | Severidad | Fichero / área |
|---|---|---|
| XSS payload histórico en `data/offsec/journal.yaml` (audit log) | Media | `data/offsec/journal.yaml` |
| Sin E2E browser tests — regresiones UI invisibles | Media | `tests/` |
| Working tree grande sin commitear (~todos los cambios post-06-08) | Alta operacional | todo el repo |
| `_SKILL_CATALOG` hardcoded en `app.js:~1801,~1953` | Baja | `web/app.js` |
| Skills matrix header hardcoded (10 IDs, `index.html:367-376`) | Baja | `web/index.html` |
| Rate limit `tenant_writes` cubre create+apply+reject (60/min puede ser bajo) | Baja | `api/security/rate_limit.py` |
| `auth_event` sin retention policy — crecimiento ilimitado | Media | `api/security/audit.py` |

### Deuda técnica visible

- `_renderNprSkillRows` y `_renderReqSkillRows` en `app.js` son ~95% idénticos (F6)
- `_escapeHtml` alias `H` duplicado por función en `app.js` (backlog audit)
- `data/offsec/journal.yaml` con 1942 líneas mezcladas (tests + reales)
- `confirm()` nativo en `wireContactModal` (~1755) — inconsistente (F12)
- `page-clients` buscador sin handler (F3)
- Badge `pending` del journal es count estático (F5)
- `estimated_hours` en modelo sin uso UI (P3 del ROADMAP)

### Preguntas abiertas

- **D1 (Línea B):** ¿Qué proveedor LLM para el chat-agente? (BLOQUEADO por API key) — requiere spike
- **D2:** ¿Next.js en algún momento o estático definitivo?
- **P3:** `estimated_hours` — usarlo en coverage o eliminarlo del modelo
- ¿Cleanup de `journal.yaml` histórico o aceptarlo como audit log?
- Admin endpoints (`/api/admin/*`): ¿UI en la próxima iteración? (D4 = sí, F11 ~6h)
