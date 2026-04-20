"""ruamel.yaml wrapper — round-trip loads (preserves comments + order).

Use `load(path)` to read a YAML file as Python data. Use `dump(path, data)`
to write back. Use `backup(path)` before a mutation to create a .bak sibling;
`restore(path)` rolls it back if ruamel chokes on the mutated structure.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

_yaml = YAML(typ="rt")
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=4, offset=2)
_yaml.width = 120


def load(path: Path) -> Any:
    """Load YAML preserving order/comments/quoting. Returns empty list if file is empty."""
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if not text.strip():
        return []
    return _yaml.load(text)


def dump(path: Path, data: Any) -> None:
    """Write YAML back preserving round-trip formatting."""
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
