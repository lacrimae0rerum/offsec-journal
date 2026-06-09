"""D3 — search filters: type, date range (notes), tags (notes).

queries.search stays backward-compatible: called with no filters it behaves as
before. New keyword filters narrow the result set. Tests are self-contained:
they append their own notes so they don't depend on seed specifics.
"""
from __future__ import annotations

from api.core import db, notes, queries, sync


def _search(team, q, **kw):
    with db.transaction() as conn:
        return queries.search(conn, team, q, **kw)


# =============================================================================
# Backward compatibility
# =============================================================================

class TestBackwardCompatible:
    def test_no_filters_returns_all_groups(self, tmp_env):
        res = _search("offsec", "hacking")
        assert "people" in res and "projects" in res and "notes" in res
        assert "total" in res["stats"]


# =============================================================================
# Type filter
# =============================================================================

class TestTypeFilter:
    def test_types_notes_only_excludes_people_and_projects(self, tmp_env):
        notes.append("person", "fer", "zztypebody marker one", "fer", "offsec", tags=["t"])
        sync.sync()
        res = _search("offsec", "zztypebody", types=["notes"])
        assert res["people"] == []
        assert res["projects"] == []
        assert len(res["notes"]) >= 1

    def test_types_people_only_excludes_notes_even_when_body_matches(self, tmp_env):
        notes.append("person", "fer", "zztypebody marker two", "fer", "offsec", tags=["t"])
        sync.sync()
        res = _search("offsec", "zztypebody", types=["people"])
        assert res["notes"] == []
        assert res["projects"] == []
        assert res["stats"]["total"] == len(res["people"])


# =============================================================================
# Date range filter (notes by timestamp)
# =============================================================================

class TestDateRangeFilter:
    def test_date_to_in_the_past_excludes_recent_note(self, tmp_env):
        notes.append("person", "fer", "zzdaterange alpha", "fer", "offsec", tags=["d"])
        sync.sync()
        assert len(_search("offsec", "zzdaterange")["notes"]) >= 1
        res = _search("offsec", "zzdaterange", date_to="2020-12-31")
        assert res["notes"] == []

    def test_date_from_in_the_past_includes_recent_note(self, tmp_env):
        notes.append("person", "fer", "zzdaterange beta", "fer", "offsec", tags=["d"])
        sync.sync()
        res = _search("offsec", "zzdaterange", date_from="2020-01-01")
        assert len(res["notes"]) >= 1

    def test_returned_notes_respect_date_from(self, tmp_env):
        notes.append("person", "fer", "zzdaterange gamma", "fer", "offsec", tags=["d"])
        sync.sync()
        res = _search("offsec", "zzdaterange", date_from="2020-01-01")
        assert all(n["timestamp"][:10] >= "2020-01-01" for n in res["notes"])


# =============================================================================
# Tags filter (notes)
# =============================================================================

class TestTagsFilter:
    def test_matching_tag_keeps_note(self, tmp_env):
        notes.append("person", "fer", "zztagbody delta", "fer", "offsec", tags=["zztag1"])
        sync.sync()
        res = _search("offsec", "zztagbody", tags=["zztag1"])
        assert len(res["notes"]) >= 1

    def test_nonexistent_tag_filters_note_out(self, tmp_env):
        notes.append("person", "fer", "zztagbody epsilon", "fer", "offsec", tags=["zztag1"])
        sync.sync()
        res = _search("offsec", "zztagbody", tags=["no_such_tag_xyz"])
        assert res["notes"] == []


# =============================================================================
# HTTP endpoint wiring (query params parsed into filters)
# =============================================================================

class TestSearchEndpointParams:
    def test_endpoint_types_param_filters_groups(self, offsec_admin_client):
        notes.append("person", "fer", "zzhttpbody zeta", "fer", "offsec", tags=["t"])
        sync.sync()
        r = offsec_admin_client.get("/api/search", params={"q": "zzhttpbody", "types": "notes"})
        assert r.status_code == 200
        body = r.json()
        assert body["people"] == []
        assert body["projects"] == []
        assert len(body["notes"]) >= 1

    def test_endpoint_tags_param_filters_notes(self, offsec_admin_client):
        notes.append("person", "fer", "zzhttpbody eta", "fer", "offsec", tags=["zzhttptag"])
        sync.sync()
        r = offsec_admin_client.get(
            "/api/search", params={"q": "zzhttpbody", "tags": "no_such_tag_xyz"}
        )
        assert r.status_code == 200
        assert r.json()["notes"] == []
