"""ruamel.yaml wrapper + path helpers for team-scoped / shared YAML files.

Primitives: `load(path)`, `dump(path, data)`, `backup(path)`, `restore(path)`.

Path helpers (post-multitenant):
    shared_path("skills")           -> <data_dir>/skills.yaml
    shared_path("teams")            -> <data_dir>/teams.yaml
    tenant_path("offsec", "people") -> <data_dir>/offsec/people.yaml

Callers never hardcode path strings; they go through the helpers so the
layout can change without code scattered through routes/queries/journal.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from api.config import settings

_yaml = YAML(typ="rt")
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 120


# ---------- primitives ----------
def load(path: Path) -> Any:
    """Load YAML preserving order/comments/quoting. Returns empty list if file is empty or absent."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.strip():
        return []
    return _yaml.load(text)


def dump(path: Path, data: Any) -> None:
    """Write YAML back preserving round-trip formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        _yaml.dump(data, fp)


def backup(path: Path) -> Path:
    """Create {path}.bak siblings for rollback. Overwrites previous .bak."""
    bak = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copy2(path, bak)
    return bak


def restore(path: Path) -> None:
    """Restore from .bak. Raises if no backup exists."""
    bak = path.with_suffix(path.suffix + ".bak")
    if not bak.exists():
        raise FileNotFoundError(f"No backup at {bak}")
    shutil.copy2(bak, path)


# ---------- path helpers ----------
SHARED_ENTITIES = frozenset({"skills", "teams"})
TENANT_ENTITIES = frozenset({
    "people", "projects", "clients",
    "assignments", "availability", "journal", "offices",
})


def shared_path(entity: str, data_dir: Path | None = None) -> Path:
    """Path to a shared-across-teams YAML (skills, teams)."""
    if entity not in SHARED_ENTITIES:
        raise ValueError(
            f"entity '{entity}' is not shared; use tenant_path(team_slug, '{entity}')"
        )
    base = Path(data_dir) if data_dir else settings.data_dir
    return base / f"{entity}.yaml"


def tenant_path(team_slug: str, entity: str, data_dir: Path | None = None) -> Path:
    """Path to a team-scoped YAML under <data_dir>/<team_slug>/<entity>.yaml."""
    if entity not in TENANT_ENTITIES:
        raise ValueError(
            f"entity '{entity}' is not tenant-scoped; use shared_path('{entity}')"
        )
    if not team_slug or "/" in team_slug or ".." in team_slug:
        raise ValueError(f"invalid team_slug: {team_slug!r}")
    base = Path(data_dir) if data_dir else settings.data_dir
    return base / team_slug / f"{entity}.yaml"
