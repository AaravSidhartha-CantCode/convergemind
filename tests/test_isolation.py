"""Tenant isolation, the Track 2 criterion most easily faked and least easily trusted."""

import uuid

from backend.db import customer_graph_key, get_customer_graph
from backend.memory_tools import recall_customer_context, record_fact, start_session


def test_one_customers_graph_cannot_see_another(tenant):
    other = f"test_{uuid.uuid4().hex[:8]}"
    try:
        session_id = start_session(tenant, agent_name="ChatAgent")
        record_fact(tenant, session_id, key="secret", value="only-for-tenant")
        start_session(other, agent_name="ChatAgent")

        # Query the other tenant's keyspace for the first tenant's data.
        leaked = get_customer_graph(other).query(
            "MATCH (f:Fact {key: 'secret'}) RETURN f.value"
        ).result_set
        assert leaked == []

        assert recall_customer_context(other)["facts"] == []
    finally:
        get_customer_graph(other).delete()


def test_graph_keys_are_namespaced_per_customer():
    assert customer_graph_key("cust_alice") == "customer:cust_alice"
    assert customer_graph_key("cust_bob") != customer_graph_key("cust_alice")


def test_agent_tools_cannot_be_steered_to_another_tenant(tenant):
    """The model never supplies customer_id; the server binds it.

    This is the prompt-injection boundary: even if the model is convinced to
    pass someone else's id, the bound dispatch ignores it.
    """
    from backend.agent import _dispatch_for

    other = f"test_{uuid.uuid4().hex[:8]}"
    try:
        session_id = start_session(tenant, agent_name="ChatAgent")
        record_fact(tenant, session_id, key="plan", value="Pro")

        other_session = start_session(other, agent_name="ChatAgent")
        record_fact(other, other_session, key="plan", value="Enterprise")

        dispatch = _dispatch_for(tenant, session_id)
        # A hostile or hallucinated argument naming the other tenant.
        result = dispatch["recall_customer_context"](customer_id=other)

        assert result["customer_id"] == tenant
        assert next(f for f in result["facts"] if f["key"] == "plan")["value"] == "Pro"
    finally:
        get_customer_graph(other).delete()
