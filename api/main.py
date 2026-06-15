"""FastAPI app entrypoint. Launches uvicorn via `make up`.

Routes (all require nginx+Authelia + local `user` row, except /api/health):
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

Auth: require_authelia reads Remote-User header (set by nginx after forward-auth
against Authelia) and looks it up in the local `user` table. The app does NOT
own user passwords/MFA; that's Authelia's job.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger

from api.config import ROOT, settings
from api.core import db
from api.routes import (
    admin,
    auth,
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
    log_path = settings.log_dir / "app.log"
    logger.add(
        log_path,
        rotation="10 MB",
        retention="7 days",
        enqueue=True,
    )
    # Lock down newly-created log files to owner-only. Loguru doesn't expose a
    # mode= arg, so we chmod after the first add()-triggered file creation.
    import os
    import stat
    try:
        if log_path.exists():
            os.chmod(log_path, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, NotImplementedError):
        pass


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _assert_dev_mode_safe() -> None:
    """Refuse to start if DEV_USER is set together with a non-loopback host.

    DEV_USER bypasses Authelia + trusted-proxy entirely; if it ever leaks into
    a production .env it would silently authenticate every caller. Aborting at
    startup makes the misconfiguration loud.

    Escape hatch: DEV_ALLOW_LAN=true acknowledges the risk and lets the dev
    server bind on a non-loopback address (e.g. 0.0.0.0) for LAN testing on
    a trusted network. The warning at startup is louder in that case.
    """
    if not settings.dev_user:
        return
    host = (settings.api_host or "").strip().lower()
    is_loopback = host in _LOOPBACK_HOSTS
    if not is_loopback and not settings.dev_allow_lan:
        raise RuntimeError(
            f"DEV_USER is set ('{settings.dev_user}') but API_HOST='{host}' is not "
            f"a loopback address. Refusing to start: this combination authenticates "
            f"every request as that user and is unsafe outside localhost. "
            f"Unset DEV_USER, bind to 127.0.0.1, or set DEV_ALLOW_LAN=true if you "
            f"are on a trusted network and accept the risk."
        )
    if is_loopback:
        logger.warning(
            "DEV_USER='{user}' active — Authelia and trusted-proxy checks are BYPASSED. "
            "Every request will authenticate as this user. Localhost-only ({host}).",
            user=settings.dev_user, host=host,
        )
    else:
        logger.warning(
            "DEV_USER='{user}' on LAN host {host} (DEV_ALLOW_LAN=true). ANY device "
            "reachable on this address authenticates as '{user}' WITHOUT credentials. "
            "Use only on trusted networks.",
            user=settings.dev_user, host=host,
        )


def create_app() -> FastAPI:
    _setup_logging()
    _assert_dev_mode_safe()
    db.init_db()

    app = FastAPI(
        title="OffSec Journal API",
        version="0.1.0",
        description="MSSP offensive security team management — YAML source-of-truth + SQLite cache",
    )

    # No CORS middleware: the frontend is served from the same origin (the
    # nginx vhost) as /api/*. Cross-origin is not a supported mode.

    # Dev-mode: prevent the browser from caching frontend assets, so JS/CSS
    # edits show up on a normal reload instead of needing Ctrl+Shift+R.
    if settings.dev_user:
        @app.middleware("http")
        async def _no_cache_static(request, call_next):
            response = await call_next(request)
            path = request.url.path
            if not path.startswith("/api/") and path != "/api":
                response.headers["Cache-Control"] = "no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
            return response

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
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

    # Serve the static frontend at / — same origin as /api means no CORS.
    # Mounted last so /api/* routes take precedence over the static files.
    web_dir = ROOT / "web"
    if web_dir.exists():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
    return app


app = create_app()
