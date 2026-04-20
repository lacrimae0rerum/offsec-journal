"""FastAPI app entrypoint. Launches uvicorn via `make up`.

Routes:
  GET  /api/health
  GET  /api/people, /api/people/{id}, /api/people/{id}/coherence
  GET  /api/projects, /api/projects/{code}
  GET  /api/clients, /api/clients/{id}
  GET  /api/skills, /api/offices, /api/geo
  GET  /api/coherence
  GET  /api/heatmap, /api/skill-gap, /api/search
  GET  /api/journal, POST /api/journal,
       POST /api/journal/{id}/apply, POST /api/journal/{id}/reject
  GET  /api/notes, POST /api/notes
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from api.config import ROOT, settings
from api.core import db
from api.routes import (
    bootstrap,
    clients,
    coherence,
    geo,
    health,
    heatmap,
    journal,
    notes,
    offices,
    people,
    projects,
    search,
    skill_gap,
    skills,
)


def _setup_logging() -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        settings.log_dir / "app.log",
        rotation="10 MB",
        retention="7 days",
        enqueue=True,
    )


def create_app() -> FastAPI:
    _setup_logging()
    db.init_db()

    app = FastAPI(
        title="OffSec Journal API",
        version="0.1.0",
        description="MSSP offensive security team management — YAML source-of-truth + SQLite cache",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "X-API-Key"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(bootstrap.router, prefix="/api")
    app.include_router(people.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(clients.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    app.include_router(offices.router, prefix="/api")
    app.include_router(geo.router, prefix="/api")
    app.include_router(coherence.router, prefix="/api")
    app.include_router(heatmap.router, prefix="/api")
    app.include_router(skill_gap.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(journal.router, prefix="/api")
    app.include_router(notes.router, prefix="/api")

    # Serve the static frontend at / — same origin as /api means no CORS, no
    # manual API key copy/paste (frontend calls /api/bootstrap first). Mounted
    # last so /api/* routes take precedence over the static files.
    web_dir = ROOT / "web"
    if web_dir.exists():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
    return app


app = create_app()
