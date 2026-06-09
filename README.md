# Offensive Security Journal

Tool interna multi-team del MSSP. Dos equipos aislados (**OffSec** e **InfoSec**) con sus propias personas, proyectos, clientes, assignments, availability, journal y notas. Catálogo de skills compartido.

Corre detrás de nginx + Authelia. La auth (password + TOTP) la hace Authelia; la app sólo autoriza (qué team, qué rol).

## Stack

| Capa | Tecnología | Estado |
|---|---|---|
| Fuente de verdad | YAML en `data/` (ruamel round-trip) | ✅ |
| Read-cache | SQLite + FTS5 (stdlib) | ✅ |
| Backend | FastAPI + pydantic v2 + loguru | ✅ 15 routers |
| Auth perímetro | Authelia (file-based users + TOTP + sessions en Postgres) | ✅ existente |
| Auth app | tabla `user` local + `Remote-User` desde nginx forward-auth | ✅ |
| Multi-tenancy | row-level `team_id` en todas las tablas tenant-scoped | ✅ |
| Admin CLI | `offsec` (entry point, `api/cli.py`) | ✅ |
| LLM | Llama 3.1 8B vía Ollama nativo | ⏳ pendiente |
| Frontend | HTML/CSS/JS estático | ✅ 12 páginas + 16 modales CRUD |
| Frontend ↔ backend | `web/api.js` con `credentials: 'include'` | ✅ |
| Rate limiting | `api/security/rate_limit.py` (60/min en mutadores) | ✅ |
| Tests | pytest + FastAPI TestClient | ✅ 176 verdes |

## Arquitectura auth (resumen)

```
Usuario → VPN / túnel → https://osj.tu-dominio.example
              ↓
           nginx 443/TLS (vhost osj.tu-dominio.example)
           ├─ auth_request → Authelia 127.0.0.1:9091
           │    ├─ sin cookie → 302 login.tu-dominio.example
           │    └─ OK → headers Remote-User/Groups/Name/Email
           ↓
         uvicorn 127.0.0.1:8000 (systemd)
           ↓ middleware require_authelia:
              1) client.host ∈ trusted_proxy_ips (nginx loopback)
              2) Remote-User no vacío
              3) SELECT en tabla user → team_id + role
           ↓
         queries con WHERE team_id = ctx.team_id
```

La app autoriza a partir de la cabecera `Remote-User` que inyecta nginx tras el forward-auth de Authelia; nunca gestiona contraseñas ni MFA.

## Quickstart (desarrollo local)

Prereq: Python 3.11+.

```bash
make install       # venv + deps + .env + sync inicial (sin secrets)
make up            # api en 127.0.0.1:8000 (sin auth — dev-only)
```

En dev local **no hay Authelia delante**, así que tienes dos opciones:

1. **Dev simple**: whitelist `testclient` y inyectar manualmente `Remote-User` con `curl`/`TestClient`:
   ```bash
   curl -H "Remote-User: fer" -H "X-Real-IP: 10.8.0.1" http://127.0.0.1:8000/api/auth/me
   ```

2. **Dev prod-like**: poner un Caddy/nginx + Authelia delante (pendiente de escribir).

Para registrar users en la app (ambos casos):
```bash
.venv/bin/offsec teams list
.venv/bin/offsec users add --username fer --team offsec --role admin --display-name "Fernando"
```

El `username` tiene que coincidir con el de Authelia en producción.

### Dev con Docker (solo local)

Hay un `docker-compose.yml` **solo para desarrollo** que levanta la app sin Authelia
(modo `DEV_USER=fer`, autoprovisionado en el team `offsec`):

```bash
docker compose up -d --build   # app en http://127.0.0.1:8001
docker compose logs -f         # ver logs
docker compose down            # parar
```

> ⚠️ **Solo local.** Este compose **bypasea la autenticación** (cualquier request entra
> como `fer`). Por eso el puerto se publica en `127.0.0.1:8001` (loopback del host,
> inalcanzable desde la LAN). Nunca lo expongas ni lo uses en producción — producción
> es systemd + nginx + Authelia.

## Layout

```
api/                       Backend FastAPI
├── main.py                entrypoint
├── config.py              Settings (pydantic-settings, .env) — sin secrets de app
├── cli.py                 CLI offsec users/teams
├── models/                pydantic v2 (Person, Project, Client, Journal...)
├── core/
│   ├── db.py              SQLite schema multi-tenant + FTS5 team_id
│   ├── yaml_io.py         ruamel round-trip + shared_path / tenant_path
│   ├── sync.py            YAML → SQLite, itera por team
│   ├── coherence.py       reglas global_level ↔ skills
│   ├── journal.py         apply/reject/create con .bak rollback + 22 handlers (todos team_slug-aware)
│   ├── queries.py         reads team-scoped + skill_gap + heatmap + FTS search
│   └── notes.py           append-only markdown por team
├── security/
│   ├── __init__.py        re-exports AuthContext, require_authelia, require_admin, log_event
│   ├── authelia.py        middleware Remote-User → AuthContext + trust check
│   └── audit.py           auth_event table + IP parsing (X-Real-IP > XFF > client.host)
└── routes/                15 routers
    ├── health.py          sin auth
    ├── auth.py            /api/auth/me (identity envelope + logout_url)
    ├── admin.py           /api/admin/users, /api/admin/auth-events (role=admin, team-scoped)
    └── ...                people / projects / clients / offices / skills / geo / coherence /
                           heatmap / skill_gap / search / journal / notes

data/                    Fuente de verdad en YAML
├── teams.yaml           seed offsec + infosec
├── skills.yaml          catálogo compartido
├── offsec/              *.yaml team-scoped (people, projects, clients, ...)
├── infosec/             ídem
└── cache.db             derivado SQLite

notes/                   Markdown append-only
├── offsec/persons/, projects/, clients/
└── infosec/persons/, projects/, clients/

web/                     Frontend (HTML/CSS/JS estático)
tests/                   pytest suite
```

## Endpoints

```
Públicos (sin auth)
  GET  /api/health

Autenticados (require_authelia)
  GET  /api/auth/me
  GET  /api/people                /api/people/:id    /api/people/:id/skills    /api/people/:id/coherence
  GET  /api/projects              /api/projects/:code
  GET  /api/clients               /api/clients/:id
  GET  /api/skills                (shared, no team scope)
  GET  /api/offices               /api/geo
  GET  /api/coherence
  GET  /api/heatmap?start=YYYY-MM-DD&end=YYYY-MM-DD
  GET  /api/skill-gap?scope=pipeline|active
  GET  /api/search?q=...
  GET  /api/journal?status=pending|applied|rejected
  POST /api/journal                               (body = JournalCreate)
  POST /api/journal/:id/apply
  POST /api/journal/:id/reject                    (body = {reason})
  GET  /api/notes?entity_type=…&entity_id=…
  POST /api/notes

Admin del team (require_admin, team-scoped)
  GET   /api/admin/users?archived=false
  POST  /api/admin/users                          (body con team opcional; si ≠ ctx → 400)
  PATCH /api/admin/users/:id                      (cross-team → 404, no 403)
  GET   /api/admin/auth-events?limit=100&offset=0&event=login_success
```

Cross-team ops (ej. mover un user de offsec a infosec) van por CLI `offsec` en el servidor; la API admin nunca permite tocar otro team.

## Entidades editables (via journal pattern)

| Entidad | Crear | Editar | Archivar | Ruta journal | Scope |
|---|---|---|---|---|---|
| Personas | ✓ | ✓ | soft | `person_create/update/archive` | team |
| Skills de persona (embebidas) | ✓ | ✓ | quitar via level 0 | `skill_update` | team |
| Proyectos | ✓ | ✓ | soft | `project_create/update/archive` | team |
| Required skills (embebidas) | ✓ | ✓ | ✓ | `project_update` | team |
| Assignments | ✓ | via unassign + new | soft (unassign) | `assign` / `unassign` | team |
| Availability (PTO/training/…) | ✓ | — | soft | `availability` | team |
| Clientes | ✓ | ✓ | soft | `client_create/update/archive` | team |
| Contactos (embebidos) | ✓ | ✓ | quitar | `contact_add/update/remove` | team |
| Oficinas | ✓ | ✓ | soft | `office_create/update/archive` | team |
| Skills catalog | ✓ | ✓ label/desc | soft | `skill_catalog_create/archive/label_update` | shared |
| Notas | ✓ append | ✗ (audit) | ✗ | direct (`POST /api/notes`) | team |

## Verificación rápida

```bash
.venv/bin/python -m api.core.sync                # rebuild cache.db
.venv/bin/python -c "from api.main import app"   # app arranca
.venv/bin/offsec teams list                      # offsec + infosec
```

## Referencias

- [ROADMAP.md](ROADMAP.md) — cuadro de mando y backlog
- [CHANGELOG.md](CHANGELOG.md) — historial de cambios (Keep a Changelog)
- [web/README.md](web/README.md) — detalles del frontend
