# OffSec Journal

Herramienta interna para gestionar equipos de seguridad ofensiva. Dos equipos aislados
(**OffSec** e **InfoSec**) con sus propias personas, proyectos, clientes, asignaciones,
disponibilidad y notas. Catálogo de skills compartido.

La fuente de verdad son ficheros YAML; SQLite es solo una caché de lectura que se reconstruye.
Toda modificación pasa por un *journal* (pendiente → aplicar/rechazar) con rollback.

## Qué hace

- **Personas**: skills por nivel, rol, disponibilidad (PTO, formación…).
- **Proyectos y clientes**: skills requeridas y asignaciones con dedicación.
- **Cobertura**: heatmap de carga y *skill-gap* (qué falta para el pipeline).
- **Búsqueda** full-text (FTS5) sobre personas, proyectos y notas, con filtros por tipo, fecha y tags.
- **Multi-tenant**: cada equipo solo ve lo suyo. La autenticación se delega en Authelia; la app solo autoriza.

## Stack

Python 3.11+ · FastAPI · SQLite (FTS5) · YAML (ruamel) · frontend HTML/CSS/JS estático.

## Uso

Local:

```bash
make install     # venv + dependencias + .env
make up          # http://127.0.0.1:8000
make test        # pytest
```

Con Docker (dev, sin Authelia delante):

```bash
docker compose up -d --build   # http://127.0.0.1:8001
```

Gestión de usuarios (Authelia autentica, la app autoriza por team y rol):

```bash
.venv/bin/offsec teams list
.venv/bin/offsec users add --username fer --team offsec --role admin
```

En dev local no hay Authelia: usa `DEV_USER` en el `.env` o inyecta la cabecera `Remote-User` por curl.

## Más

- [ROADMAP.md](ROADMAP.md) — estado y backlog.
- [CHANGELOG.md](CHANGELOG.md) — cambios.
