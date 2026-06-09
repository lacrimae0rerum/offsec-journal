"""Notes append-only + FTS5 search round-trip."""
from api.core import db, notes, sync


def test_append_creates_markdown_block(tmp_env):
    note = notes.append("person", "santi", "Nota nueva sobre AD", "fer", "offsec", tags=["ad", "mentor"])
    assert note["author"] == "fer"
    read_back = notes.read_all("person", "santi", "offsec")
    assert any("Nota nueva sobre AD" in n["body"] for n in read_back)
    assert any(set(n["tags"]) >= {"ad", "mentor"} for n in read_back)


def test_append_never_overwrites(tmp_env):
    notes.append("person", "santi", "primera", "fer", "offsec")
    notes.append("person", "santi", "segunda", "fer", "offsec")
    notes.append("person", "santi", "tercera", "fer", "offsec")
    blocks = notes.read_all("person", "santi", "offsec")
    bodies = [n["body"] for n in blocks]
    assert "primera" in bodies
    assert "segunda" in bodies
    assert "tercera" in bodies


def test_append_rejects_empty(tmp_env):
    import pytest
    with pytest.raises(ValueError):
        notes.append("person", "santi", "   ", "fer", "offsec")


def test_fts_finds_appended_note_after_sync(tmp_env):
    notes.append("project", "PT-2026-018", "Frontera AWS lambda pendiente", "fer", "offsec", tags=["aws"])
    sync.sync()  # rebuild FTS index
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT entity_id, body FROM notes_fts WHERE notes_fts MATCH ? AND team_id = ?",
            ('"lambda"', "offsec"),
        ).fetchall()
    assert any("lambda" in r["body"].lower() for r in rows)


def test_fts_tokenizer_handles_diacritics(tmp_env):
    """The unicode61 tokenizer with remove_diacritics=2 should match 'evolucion' → 'evolución'."""
    sync.sync()  # make sure seed notes are indexed
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT body FROM notes_fts WHERE notes_fts MATCH ? AND team_id = ?",
            ('"evolucion"', "offsec"),
        ).fetchall()
    assert len(rows) >= 1


def test_queries_search_returns_grouped(tmp_env):
    from api.core import queries
    with db.transaction() as conn:
        result = queries.search(conn, "offsec", "hacking")
    assert "people" in result and "projects" in result and "notes" in result
    assert result["stats"]["total"] >= 0


def test_parser_handles_hyphen_tags(tmp_env, tmp_path):
    """Regression BUG-007: tags with hyphens (e.g. 'client-delta') previously
    broke the separator regex and caused subsequent notes to disappear."""
    from api.core.sync import _parse_markdown_notes
    md = tmp_path / "tricky.md"
    md.write_text(
        "--- 2026-04-15T10:00:00Z | fer | tags: mentoring, osint ---\n"
        "First note\n\n"
        "--- 2026-04-02T14:30:00Z | fer | tags: cti, client-delta, post-mortem ---\n"
        "Middle note with hyphenated tags\n\n"
        "--- 2026-03-20T08:15:00Z | santi | tags: pto ---\n"
        "Third note\n",
        encoding="utf-8",
    )
    notes = _parse_markdown_notes(md)
    assert len(notes) == 3
    middle = notes[1]
    assert middle["author"] == "fer"
    assert "client-delta" in middle["tags"]
    assert "post-mortem" in middle["tags"]
    assert middle["body"] == "Middle note with hyphenated tags"
