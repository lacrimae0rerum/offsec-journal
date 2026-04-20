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
API_HOST ?= 0.0.0.0
API_PORT ?= 8000

help:
	@echo "offsec-journal — targets:"
	@echo "  install   create venv, install deps, generate API key"
	@echo "  up        start api + frontend on :$(API_PORT) (all-in-one)"
	@echo "  sync      rebuild SQLite cache from data/*.yaml"
	@echo "  test      run pytest suite"
	@echo "  doctor    verify env (ollama, python, ports)"
	@echo "  reset     wipe SQLite cache (backups kept)"
	@echo "  web       serve only the static frontend on :3000 (dev, rarely needed)"

install:
	@if [ ! -x "$(VENV_PY)" ]; then \
		echo "→ Creating virtualenv at $(VENV) using $(SYSTEM_PYTHON)"; \
		$(SYSTEM_PYTHON) -m venv $(VENV) || (echo "venv creation failed — try: sudo apt install python3-venv"; exit 1); \
	fi
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[dev]"
	@if [ ! -f .env ]; then \
		KEY=$$($(VENV_PY) -c 'import secrets;print(secrets.token_urlsafe(32))'); \
		echo "API_KEY=$$KEY" > .env; \
		echo "OLLAMA_URL=http://localhost:11434" >> .env; \
		echo "API_HOST=0.0.0.0" >> .env; \
		echo "API_PORT=8000" >> .env; \
		echo "DB_PATH=./data/cache.db" >> .env; \
		echo "DATA_DIR=./data" >> .env; \
		echo "NOTES_DIR=./notes" >> .env; \
		echo "LOG_DIR=./logs" >> .env; \
		echo ""; \
		echo "=============================================="; \
		echo " API_KEY written to .env — $$KEY"; \
		echo "=============================================="; \
	fi
	@$(MAKE) sync

sync:
	$(PYTHON) -m api.core.sync

up:
	$(PYTHON) -m uvicorn api.main:app --host $(API_HOST) --port $(API_PORT) --reload

test:
	$(PYTHON) -m pytest -v

doctor:
	$(PYTHON) -m api.doctor

reset:
	rm -f ./data/cache.db
	$(MAKE) sync

web:
	$(PYTHON) -m http.server 3000 --directory web
