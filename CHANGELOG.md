# Changelog

Todos los cambios notables de OffSec Journal se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/)
y el proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased] - 2026-06-15

Cambios en el working tree, todavía sin commitear.

### Added
- **Admin UI (D4/F11):** página `/admin` con gestión de usuarios del team (crear usuario,
  cambiar rol member↔admin, archivar/desarchivar) y tabla de auth-events con filtro por
  tipo de evento y paginación. Implementado como frontend puro sobre los endpoints
  `/api/admin/users` y `/api/admin/auth-events` ya existentes.
- 12 tests de integración (`tests/test_admin_ui_endpoints.py`) que verifican el contrato
  del backend que consume la Admin UI: listado paginado, filtro por tipo de evento,
  creación de usuario, cambio de rol y archivado.
- `ROADMAP.md` y `CHANGELOG.md`.
- Setup Docker de desarrollo (`Dockerfile`, `docker-compose.yml`, `.dockerignore`).
- Flag `DEV_ALLOW_LAN` en `api/config.py` y `api/main.py`: escape hatch explícito para
  exponer el modo `dev_user` (bypass de Authelia) a una IP de LAN en redes de confianza,
  con warning reforzado al arranque.

### Changed
- Documentación: corregidas cifras desactualizadas de tests (→ 188) y nº de modales
  (14 → 16) en `README.md` y `web/README.md`; añadida fila de rate limiting al stack.
- Búsqueda (D3): `/api/search` extendido con filtros `types`/`date_from`/`date_to`/`tags`;
  aside de filtros del frontend wireado.

### Fixed
- **Formato de id/code, campos vacíos, email y sobre-asignación (BUG-APP-003/004/005):**
  los payloads de creación del journal no validaban el formato de identificadores que sí
  exigen los modelos de lectura. Añadidos `Field(pattern=...)` a `person_create.id`,
  `client_create.id`, `skill_catalog_create.id` (snake_case) y `project_create.code`
  (`^[A-Z]{2,4}-\d{4}-\d{3}$`); validador de no-vacío en `full_name`/`name`/`label_es`;
  validación de formato de email en `contact_add`/`contact_update`. Nueva regla de
  coherencia `over_allocation` (`api/core/coherence.py` + `queries.list_assignments`):
  avisa cuando la dedicación agregada de asignaciones solapadas supera el 100%. Tests en
  `tests/test_handlers_all.py`.
- **Rangos de fecha invertidos y validación temprana (BUG-APP-002):** `assign`,
  `availability` y `project_create/update` aceptaban *y aplicaban* rangos con fin
  anterior al inicio (datos inválidos en BD). Añadidos validadores `start <= end` en los
  modelos Pydantic (`api/models/journal.py`). Además, varias comprobaciones que solo
  ocurrían en apply (duplicados de person/client/project/office/skill, `assign` duplicado
  activo, `unassign` sin asignación activa, `contact_index` fuera de rango) se han subido
  a `create_entry` (`_check_referenced_entities`), de modo que devuelven un 400 legible y
  no dejan entradas `pending` inaplicables. Tests nuevos en `tests/test_handlers_all.py`;
  `tests/test_rollback.py` actualizado al nuevo contrato (rechazo en create).
- **Validación de skill_id en el catálogo (BUG-APP-001):** `_check_referenced_entities`
  no comprobaba que el `skill_id` referenciado existiera en el catálogo compartido
  (`data/skills.yaml`). Una entrada `skill_update`, `skill_label_update` o un
  `project_create/update` con `required_skills` apuntando a una skill inexistente se
  aceptaba en `POST /api/journal` (HTTP 200, quedaba `pending`) y solo fallaba al aplicar
  con un error opaco `FOREIGN KEY constraint failed`. Ahora el create devuelve 400 con un
  mensaje legible (`skill '<id>' not found in catalog`). 4 tests nuevos en
  `tests/test_handlers_all.py`.
- **Skills dropdown:** los desplegables de asignación de skills (persona y required skills
  de proyecto) usaban una lista hardcodeada de 20 skills en el frontend; las skills nuevas
  creadas y aprobadas vía Journal nunca aparecían. Sustituido por `DATA.skills` (catálogo
  vivo cargado desde `/api/skills`) en `openEditSkill()`, `_renderReqSkillRows()` y
  `_renderNprSkillRows()`.
- **H2:** 403 en `/admin` ya no destruye el DOM; los bloques se ocultan y se restauran
  automáticamente en la siguiente carga exitosa (`_renderAdminForbidden` + `_restoreAdminContent`).
- **H5:** paginación de auth-events usa el campo `total` de la respuesta para calcular si
  existe página siguiente; se elimina el falso «siguiente deshabilitado» cuando la última
  página es exactamente múltiplo del límite.
- **H7:** `loadAdminPage` ignora llamadas concurrentes mediante flag `_loading` para evitar
  race condition en cargas solapadas.
- **H8:** nombres de eventos de auditoría en el filtro del select alineados con los valores
  reales devueltos por el backend (p. ej. `login_ok` en lugar de `login_success`).

### Removed
- Documentación interna y de proceso del repositorio (planes, threat model, spec original).

## [0.1.0] - 2026-04-27

Primera versión funcional: herramienta interna multi-team (OffSec + InfoSec),
detrás de nginx + Authelia, con 176 tests verdes.

### Added
- **Backend FastAPI** con 15 routers y 22 handlers de journal (`api/core/journal.py`),
  todos team-scope aware (people, projects, clients, offices, skills, assignments,
  availability, journal, notes, search, heatmap, skill-gap, coherence, geo, auth, admin, health).
- **Fuente de verdad YAML** (`data/`) con ruamel round-trip + read-cache SQLite/FTS5
  reconstruible (`api/core/sync.py`).
- **Journal pattern**: toda mutación pasa por `pending → apply/reject` con rollback `.bak`.
- **Multi-tenancy** row-level (`team_id`) en todas las tablas tenant-scoped; aislamiento
  cross-team end-to-end cubierto por tests.
- **Autenticación perimetral Authelia**: middleware `require_authelia` (trust proxy +
  `Remote-User` → `AuthContext` con team_id/role).
- **Audit log** (`auth_event`) con 9 tipos de evento y parsing de IP (X-Real-IP > XFF > client.host).
- **Rate limiting** (`api/security/rate_limit.py`): 60/min en mutadores tenant.
- **CLI `offsec`** (`api/cli.py`) para gestión de users/teams y ops cross-team.
- **Endpoints admin** team-scoped: `/api/admin/users`, `/api/admin/auth-events`.
- **Frontend estático** (HTML/CSS/JS): 12 páginas + 16 modales CRUD, drawer, identity block.
- Documentación: `README.md`, `web/README.md`.
- Suite de **176 tests** (pytest + FastAPI TestClient).

### Changed
- Refactor a queries team-scoped + journal team-aware; eliminada la auth legacy (X-API-Key).
- Frontend dinámico y workflow de assign/unassign mejorado (sprint UX + hardening del 27-abr).

### Removed
- Autenticación legacy basada en X-API-Key (sustituida por Authelia forward-auth).

### Security
- Hardening del sprint del 27-abr (8 hallazgos ALTOS de auditoría) + audit log + rate limiter.

---

## Pivotes respecto a la spec original

Decisiones tomadas durante el desarrollo respecto a la spec original (ver ROADMAP §2):

- **LLM chat con Ollama (tool-loop + streaming)**: no implementado (página `chat` es mock). _Decisión D1 pendiente._
- **Frontend Next.js 14 + shadcn + Recharts** → HTML/CSS/JS estático. _Decisión D2 pendiente._
- **Docker Compose** → systemd nativo.
- **Añadido al alcance original**: multi-tenant + Authelia + audit log.

[Unreleased]: https://github.com/  (repo local, sin remoto configurado)
[0.1.0]: commit 4d3a779
