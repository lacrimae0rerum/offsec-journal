# OffSec Journal — DEV image.
#
# WARNING: intended for local development/validation only. The accompanying
# docker-compose.yml runs the app with DEV_USER set, which BYPASSES Authelia
# and the trusted-proxy check entirely (every request is authenticated as that
# user). Never deploy this image to a reachable network. Production uses systemd
# behind nginx + Authelia (see DEPLOY.md).

FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir uv && uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml ./
COPY api ./api
RUN uv pip install --no-cache .

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY api ./api
COPY web ./web
COPY data ./data
COPY notes ./notes
RUN useradd --create-home app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1
# Rebuild the SQLite cache from YAML on every start, then serve.
CMD ["sh", "-c", "python -m api.core.sync && exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
