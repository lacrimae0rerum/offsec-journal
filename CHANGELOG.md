# Changelog

Todos los cambios notables de OffSec Journal se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.1.0/)
y el proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

Cambios en el working tree, todavía sin commitear.

### Changed
- Documentación: corregidas cifras desactualizadas de tests (→ 188) y nº de modales
  (14 → 16) en `README.md` y `web/README.md`; añadida fila de rate limiting al stack.
- Búsqueda (D3): `/api/search` extendido con filtros `types`/`date_from`/`date_to`/`tags`;
  aside de filtros del frontend wireado.

### Added
- `ROADMAP.md` y `CHANGELOG.md`.
- Setup Docker de desarrollo (`Dockerfile`, `docker-compose.yml`, `.dockerignore`).
- Flag `DEV_ALLOW_LAN` en `api/config.py` y `api/main.py`: escape hatch explícito para
  exponer el modo `dev_user` (bypass de Authelia) a una IP de LAN en redes de confianza,
  con warning reforzado al arranque.

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
