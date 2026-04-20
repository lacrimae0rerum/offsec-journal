"""Shared fixtures: tmp data_dir seeded from repo YAML, isolated SQLite."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from api import config as config_module


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_env(tmp_path, monkeypatch):
    """Copy data/ + notes/ into tmp and point settings at them."""
    data_dir = tmp_path / "data"
    notes_dir = tmp_path / "notes"
    db_path = tmp_path / "cache.db"

    shutil.copytree(ROOT / "data", data_dir)
    # copy notes if present
    src_notes = ROOT / "notes"
    if src_notes.exists():
        shutil.copytree(src_notes, notes_dir)
    else:
        notes_dir.mkdir()

    monkeypatch.setattr(config_module.settings, "data_dir", data_dir)
    monkeypatch.setattr(config_module.settings, "notes_dir", notes_dir)
    monkeypatch.setattr(config_module.settings, "db_path", db_path)

    from api.core import sync as sync_mod
    sync_mod.sync()

    return {"data_dir": data_dir, "notes_dir": notes_dir, "db_path": db_path}
