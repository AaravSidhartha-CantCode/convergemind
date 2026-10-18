"""Randomized sandbox for the Memory Guardian's invalidation path.

This is deliberately database-free so it can run where FalkorDB is not
available. It drives the production ``verify_memory_claim`` function against
a minimal in-memory graph double and checks its contract across varied claim,
decision, and handoff dependency layouts. FalkorDB integration remains covered
by the normal database-backed suite when the service is available.
"""

from __future__ import annotations

import random
from types import SimpleNamespace
from unittest.mock import patch

from backend.memory_tools import verify_memory_claim


class GuardianSandboxGraph:
    """Small query double for the five queries used by verification."""

    def __init__(self, claims, decisions_by_claim, handoffs_by_claim):
        self.claims = claims
        self.decisions_by_claim = decisions_by_claim
        self.handoffs_by_claim = handoffs_by_claim
        self.invalidated_decisions = set()
        self.invalidated_handoffs = set()
        self.fact_projection = {}

    def query(self, statement, params=None):
        params = params or {}
        if "RETURN m.key, m.value, m.status" in statement:
            claim = self.claims.get(params["mid"])
            rows = [[claim["key"], claim["value"], claim["status"]]] if claim else []
            return SimpleNamespace(result_set=rows)
        if "SET m.status = 'verified'" in statement:
            self.claims[params["mid"]]["status"] = "verified"
            return SimpleNamespace(result_set=[])
        if "MERGE (c)-[:HAS_FACT]" in statement:
            self.fact_projection[params["key"]] = params["value"]
            return SimpleNamespace(result_set=[])
        if "SET old.status = 'superseded'" in statement:
            current = self.claims[params["mid"]]
            rows = []
            for claim_id, claim in self.claims.items():
                if (
                    claim_id != params["mid"]
                    and claim["key"] == current["key"]
                    and claim["status"] == "verified"
                    and claim["value"] != current["value"]
                ):
                    claim["status"] = "superseded"
                    rows.append([claim_id])
            return SimpleNamespace(result_set=rows)
        if "<-[:DEPENDS_ON]-(d:Decision)" in statement:
            rows = []
            for claim_id, claim in self.claims.items():
                if claim["status"] == "superseded":
                    for decision_id, text in self.decisions_by_claim.get(claim_id, []):
                        self.invalidated_decisions.add(decision_id)
                        rows.append([decision_id, text])
            return SimpleNamespace(result_set=rows)
        if "-[:CAPTURED_IN]->(h:HandoffCapsule)" in statement:
            rows = []
            for claim_id, claim in self.claims.items():
                if claim["status"] == "superseded":
                    for handoff_id in self.handoffs_by_claim.get(claim_id, []):
                        self.invalidated_handoffs.add(handoff_id)
                        rows.append([handoff_id])
            return SimpleNamespace(result_set=rows)
        raise AssertionError(f"Unexpected production query in sandbox: {statement}")


def test_randomized_blast_radius_sandbox():
    rng = random.Random(1729)
    for _ in range(75):
        old_count = rng.randint(1, 6)
        claims = {
            f"old-{index}": {
                "key": "known_blocker",
                "value": f"old-state-{index}",
                "status": "verified",
            }
            for index in range(old_count)
        }
        claims["same-value"] = {
            "key": "known_blocker",
            "value": "new-state",
            "status": "verified",
        }
        claims["other-key"] = {"key": "plan", "value": "Pro", "status": "verified"}
        claims["replacement"] = {
            "key": "known_blocker",
            "value": "new-state",
            "status": "proposed",
        }
        decisions_by_claim = {
            claim_id: [(f"decision-{claim_id}-{n}", f"Decision {n}") for n in range(rng.randint(0, 3))]
            for claim_id in claims
        }
        handoffs_by_claim = {
            claim_id: [f"handoff-{claim_id}-{n}" for n in range(rng.randint(0, 3))]
            for claim_id in claims
        }
        graph = GuardianSandboxGraph(claims, decisions_by_claim, handoffs_by_claim)

        with patch("backend.memory_tools.get_customer_graph", return_value=graph):
            outcome = verify_memory_claim("sandbox", "replacement")

        expected_superseded = {f"old-{index}" for index in range(old_count)}
        expected_decisions = {
            decision_id
            for claim_id in expected_superseded
            for decision_id, _ in decisions_by_claim[claim_id]
        }
        expected_handoffs = {
            handoff_id
            for claim_id in expected_superseded
            for handoff_id in handoffs_by_claim[claim_id]
        }

        assert set(outcome["superseded_claim_ids"]) == expected_superseded
        assert {d["id"] for d in outcome["blast_radius"]["decisions"]} == expected_decisions
        assert set(outcome["blast_radius"]["handoff_capsule_ids"]) == expected_handoffs
        assert graph.invalidated_decisions == expected_decisions
        assert graph.invalidated_handoffs == expected_handoffs
        assert graph.fact_projection["known_blocker"] == "new-state"
