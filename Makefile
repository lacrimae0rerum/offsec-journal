.PHONY: install up down sync test doctor reset web help

# Python + venv handling.
# - `install` creates .venv if missing and installs into it (PEP 668 safe).
# - All other targets use .venv/bin/python automatically once it exists.
# - Users can still override with `make up PYTHON=/path/to/python`.
VENV := .venv
ifeq ($(OS),Windows_NT)
  VENV_PY := $(VENV)/Scripts/python.exe
else
  VENV_PY := $(VENV)/bin/python
endif
SYSTEM_PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null || echo python)
PYTHON ?= $(shell [ -x "$(VENV_PY)" ] && echo "$(VENV_PY)" || echo "$(SYSTEM_PYTHON)")
PIP ?= $(PYTHON) -m pip
API_HOST ?= 127.0.0.1
API_PORT ?= 8000

help:
	@echo "offsec-journal — targets:"
	@echo "  install   create venv, install deps, generate .env (no secrets)"
	@echo "  up        start api on :$(API_PORT) bound to 127.0.0.1 (behind nginx+Authelia in prod)"
	@echo "  sync      rebuild SQLite cache from data/*.yaml"
	@echo "  test      run pytest suite"
	@echo "  reset     wipe SQLite cache (YAML preserved)"
	@echo "  web       serve only the static frontend on :3000 (dev, rarely needed)"
	@echo ""
	@echo "User management (after install + sync):"
	@echo "  .venv/bin/offsec teams list"
	@echo "  .venv/bin/offsec users add --username <u> --team <offsec|infosec> --role <admin|member>"

install:
	@if [ ! -x "$(VENV_PY)" ]; then \
		echo "→ Creating virtualenv at $(VENV) using $(SYSTEM_PYTHON)"; \
		$(SYSTEM_PYTHON) -m venv $(VENV) || (echo "venv creation failed — try: sudo apt install python3-venv"; exit 1); \
	fi
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[dev]"
	@if [ ! -f .env ]; then \
		echo "TRUSTED_PROXY_IPS=127.0.0.1" > .env; \
		echo "API_HOST=127.0.0.1" >> .env; \
		echo "API_PORT=8000" >> .env; \
		echo "DB_PATH=./data/cache.db" >> .env; \
		echo "DATA_DIR=./data" >> .env; \
		echo "NOTES_DIR=./notes" >> .env; \
		echo "LOG_DIR=./logs" >> .env; \
		echo "# AUTHELIA_LOGOUT_URL=" >> .env; \
		chmod 600 .env || true; \
		echo ""; \
		echo "=============================================="; \
		echo " .env written — auth is delegated to nginx+Authelia; no app-side secrets."; \
		echo " Register users once Authelia has them: .venv/bin/offsec users add ..."; \
		echo "=============================================="; \
	fi
	@$(MAKE) sync

sync:
	$(PYTHON) -m api.core.sync

up:
	$(PYTHON) -m uvicorn api.main:app --host $(API_HOST) --port $(API_PORT) --reload --no-proxy-headers

test:
	$(PYTHON) -m pytest -v

reset:
	rm -f ./data/cache.db
	$(MAKE) sync

web:
	$(PYTHON) -m http.server 3000 --directory web
