"""Append-only markdown notes (decision #4).

Files live under notes/persons/<id>.md, notes/projects/<code>.md,
notes/clients/<id>.md. Each note is a block:

    --- <ISO ts> | <author> | tags: <csv> ---
    <body, free markdown>

append() never rewrites existing blocks. The FTS5 table is rebuilt on sync()
so new notes are searchable after a sync/journal-apply.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from api.config import settings


ENTITY_DIR = {
    "person": "persons",
    "project": "projects",
    "client": "clients",
}


def _target_path(entity_type: str, entity_id: str) -> Path:
    sub = ENTITY_DIR.get(entity_type)
    if sub is None:
        raise ValueError(f"invalid entity_type '{entity_type}'")
    base = settings.notes_dir / sub
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{entity_id}.md"


def append(entity_type: str, entity_id: str, body: str, author: str, tags: list[str] | None = None) -> dict:
    if not body or not body.strip():
        raise ValueError("note body cannot be empty")
    path = _target_path(entity_type, entity_id)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tag_csv = ", ".join((t.strip() for t in (tags or []) if t.strip()))
    sep = f"--- {ts} | {author} | tags: {tag_csv} ---"
    block = f"{sep}\n{body.strip()}\n\n"
    mode = "a" if path.exists() else "w"
    with path.open(mode, encoding="utf-8") as fp:
        if mode == "a" and path.stat().st_size > 0:
            fp.write("\n")
        fp.write(block)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "timestamp": ts,
        "author": author,
        "tags": tags or [],
        "body": body.strip(),
    }


def read_all(entity_type: str, entity_id: str) -> list[dict]:
    """Parse all blocks in the target markdown file. Returns empty list if no file."""
    from api.core.sync import _parse_markdown_notes  # reuse parser
    path = _target_path(entity_type, entity_id)
    if not path.exists():
        return []
    return _parse_markdown_notes(path)
