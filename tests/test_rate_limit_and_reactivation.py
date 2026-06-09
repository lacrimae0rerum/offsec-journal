"""N0.5 — coverage gaps from the ROADMAP.

1. tenant_writes rate limit (60/min) on POST /api/journal: the 61st request
   within the window must return HTTP 429 with a Retry-After header.
2. assign reactivation: re-assigning the same (person, project, start) after an
   unassign must reactivate the archived row in place, not create a duplicate.
"""
from __future__ import annotations

from api.core import db, journal
from api.security.rate_limit import reset_for_tests, tenant_writes


# =============================================================================
# tenant_writes rate limit on journal mutations
# =============================================================================

class TestJournalRateLimit:
    def test_create_throttled_after_60(self, offsec_admin_client):
        """60 journal creates within the window pass; the 61st returns 429."""
        reset_for_tests()
        try:
            body = {
                "kind": "assign",
                "payload": {
                    "person_id": "tbd_02", "project_code": "RES-2026-001",
                    "dedication_pct": 10, "start": "2026-07-01",
                    "end": "2026-07-08", "role": "executor",
                },
            }
            for i in range(tenant_writes._max):  # 60 by config
                r = offsec_admin_client.post("/api/journal", json=body)
                assert r.status_code < 400, f"create {i}: {r.status_code} {r.text}"
            # The 61st is over budget.
            r = offsec_admin_client.post("/api/journal", json=body)
            assert r.status_code == 429
            assert "Retry-After" in r.headers
            assert int(r.headers["Retry-After"]) >= 1
            assert "rate limit" in r.json()["detail"].lower()
        finally:
            reset_for_tests()


# =============================================================================
# assign reactivation of an archived (person, project, start) triple
# =============================================================================

class TestAssignReactivation:
    def _apply(self, kind, payload, team="offsec"):
        entry = journal.create_entry(kind, payload, team, proposer="human")
        journal.apply_entry(entry["id"], team, applied_by="test")
        return entry

    def test_reassign_same_triple_reactivates_in_place(self, tmp_env):
        triple = {"person_id": "tbd_02", "project_code": "RES-2026-001", "start": "2026-08-01"}

        # 1. Initial assignment.
        self._apply("assign", {**triple, "dedication_pct": 30,
                                "end": "2026-08-10", "role": "executor"})
        # 2. Unassign archives it.
        self._apply("unassign", {"person_id": triple["person_id"],
                                 "project_code": triple["project_code"]})
        # 3. Re-assign the same (person, project, start) with new attrs.
        self._apply("assign", {**triple, "dedication_pct": 55,
                                "end": "2026-08-20", "role": "shadow"})

        with db.transaction() as conn:
            rows = conn.execute(
                """SELECT dedication_pct, role, archived FROM assignment
                   WHERE person_id=? AND project_code=? AND start=?""",
                (triple["person_id"], triple["project_code"], triple["start"]),
            ).fetchall()

        # Reactivated in place: exactly one row for the triple, active, new attrs.
        assert len(rows) == 1, f"expected reactivation in place, got {len(rows)} rows"
        assert rows[0]["archived"] == 0
        assert rows[0]["dedication_pct"] == 55
        assert rows[0]["role"] == "shadow"
