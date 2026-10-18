from backend.db import get_customer_graph
from backend.memory_tools import (
    find_similar_resolutions,
    graph_snapshot,
    handoff_session,
    known_issue_types,
    log_resolution,
    recall_customer_context,
    record_fact,
    start_session,
)
import pytest
from unittest.mock import patch


def test_start_session_creates_customer_and_session(tenant):
    session_id = start_session(tenant, agent_name="ChatAgent")
    rows = get_customer_graph(tenant).query(
        """
        MATCH (c:Customer {id: $cid})-[:HAD_SESSION]->(s:Session {id: $sid})
              -[:HANDLED_BY]->(a:Agent)
        RETURN s.id, a.name
        """,
        {"cid": tenant, "sid": session_id},
    ).result_set
    assert rows[0][0] == session_id
    assert rows[0][1] == "ChatAgent"


def test_record_fact_is_recalled_with_provenance(tenant):
    session_id = start_session(tenant, agent_name="ChatAgent")
    record_fact(tenant, session_id, key="plan", value="Pro")

    context = recall_customer_context(tenant)
    plan = next(f for f in context["facts"] if f["key"] == "plan")
    assert plan["value"] == "Pro"
    assert plan["learned_by"] == ["ChatAgent"]


def test_record_fact_updates_rather_than_duplicates(tenant):
    session_id = start_session(tenant, agent_name="ChatAgent")
    record_fact(tenant, session_id, key="plan", value="Free")
    record_fact(tenant, session_id, key="plan", value="Enterprise")

    facts = [f for f in recall_customer_context(tenant)["facts"] if f["key"] == "plan"]
    assert len(facts) == 1
    assert facts[0]["value"] == "Enterprise"


def test_handoff_chains_sessions_and_second_agent_inherits_memory(tenant):
    first = start_session(tenant, agent_name="ChatAgent")
    record_fact(tenant, first, key="known_blocker", value="cannot receive SMS abroad")

    second = handoff_session(tenant, from_session=first, to_agent="EmailAgent")

    context = recall_customer_context(tenant)
    assert len(context["sessions"]) == 2
    assert context["sessions"][-1]["handled_by"] == "EmailAgent"
    # The receiving agent sees the fact it never learned itself.
    blocker = next(f for f in context["facts"] if f["key"] == "known_blocker")
    assert blocker["learned_by"] == ["ChatAgent"]

    chained = get_customer_graph(tenant).query(
        "MATCH (:Session {id: $a})-[:NEXT]->(:Session {id: $b}) RETURN 1",
        {"a": first, "b": second},
    ).result_set
    assert chained, ":NEXT edge was not created"


def test_handoff_rejects_unknown_session(tenant):
    start_session(tenant, agent_name="ChatAgent")
    with pytest.raises(ValueError):
        handoff_session(tenant, from_session="does-not-exist", to_agent="EmailAgent")


def test_resolution_is_reusable_by_a_different_customer(tenant, issue_type):
    session_id = start_session(tenant, agent_name="ChatAgent")
    log_resolution(
        tenant,
        session_id,
        issue_type=issue_type,
        resolution_text="Refunded the duplicate charge.",
    )

    # A completely separate tenant retrieves the fix.
    matches = find_similar_resolutions(issue_type=issue_type)
    assert any("Refunded the duplicate charge." == m["resolution_text"] for m in matches)
    assert matches[0]["learned_while_helping"] == tenant


def test_resolution_is_recorded_in_the_customers_own_history(tenant, issue_type):
    session_id = start_session(tenant, agent_name="ChatAgent")
    log_resolution(
        tenant, session_id, issue_type=issue_type, resolution_text="Cleared stale lock."
    )

    issues = recall_customer_context(tenant)["past_issues"]
    assert issues[0]["type"] == issue_type
    assert issues[0]["resolved_with"] == "Cleared stale lock."


def test_reuse_count_increments_once_per_retrieval(tenant, issue_type):
    session_id = start_session(tenant, agent_name="ChatAgent")
    log_resolution(tenant, session_id, issue_type=issue_type, resolution_text="Fix.")

    find_similar_resolutions(issue_type=issue_type)
    find_similar_resolutions(issue_type=issue_type)
    matches = find_similar_resolutions(issue_type=issue_type)
    assert matches[0]["reuse_count"] == 3


def test_known_issue_types_includes_logged_type(tenant, issue_type):
    session_id = start_session(tenant, agent_name="ChatAgent")
    log_resolution(tenant, session_id, issue_type=issue_type, resolution_text="Fix.")
    assert issue_type in known_issue_types()


def test_graph_snapshot_returns_nodes_and_edges(tenant):
    session_id = start_session(tenant, agent_name="ChatAgent")
    record_fact(tenant, session_id, key="plan", value="Pro")

    snapshot = graph_snapshot(tenant)
    labels = {node["label"] for node in snapshot["nodes"]}
    assert {"Customer", "Session", "Agent", "Fact"} <= labels
    assert {"HAD_SESSION", "HANDLED_BY", "HAS_FACT", "LEARNED"} <= {
        edge["type"] for edge in snapshot["edges"]
    }
    plan_node = next(n for n in snapshot["nodes"] if n["label"] == "Fact")
    assert plan_node["caption"] == "plan: Pro"


def test_claim_recall_projects_sort_field_after_aggregation():
    """FalkorDB requires ORDER BY fields to be in an aggregate RETURN scope."""
    queries = []

    class Result:
        def __init__(self, rows):
            self.result_set = rows

    class Graph:
        def query(self, cypher, _params):
            queries.append(cypher)
            if "MemoryClaim" in cypher:
                return Result(
                    [["claim_1", "plan", "Pro", "verified", 1.0, "case", ["case record"], "2026-01-01"]]
                )
            return Result([])

    with patch("backend.memory_tools.get_customer_graph", return_value=Graph()):
        context = recall_customer_context("cust_test")

    claim_query = next(query for query in queries if "MemoryClaim" in query)
    assert "collect(DISTINCT e.text), m.created_at" in claim_query
    assert "ORDER BY m.created_at DESC" in claim_query
    assert context["claims"] == [
        {
            "id": "claim_1",
            "key": "plan",
            "value": "Pro",
            "status": "verified",
            "source_trust": 1.0,
            "source_type": "case",
            "evidence": ["case record"],
        }
    ]
