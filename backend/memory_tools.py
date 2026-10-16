"""The agent memory layer. Every function here is one named Cypher query.

Three memory types, three different shapes in the graph:

  episodic   (Session)-[:NEXT]->(Session)        what happened, in order
  semantic   (Customer)-[:HAS_FACT]->(Fact)      what is true about this customer
  procedural (Resolution)-[:APPLIES_TO]->(IssueType)   what works, for anyone

The first two live in the customer's own graph key. The third lives in a
single shared graph key, which is the whole point: a resolution learned
while helping one customer is retrievable by an agent helping a different
customer, and that retrieval is a graph traversal, not a text search.

Full data model:

  (Customer)-[:HAD_SESSION]->(Session)-[:HANDLED_BY]->(Agent)
  (Session)-[:NEXT]->(Session)
  (Session)-[:RAISED]->(Issue)
  (Customer)-[:HAS_FACT]->(Fact)<-[:LEARNED]-(Session)
  (Resolution)-[:APPLIES_TO]->(IssueType)        [shared graph]
"""

import uuid
from datetime import datetime, timezone

from backend.db import get_customer_graph, get_shared_graph
from backend.schema import apply_customer_schema, apply_shared_schema


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_session(customer_id: str, agent_name: str) -> str:
    """Open a fresh session for a customer, handled by one agent persona."""
    graph = get_customer_graph(customer_id)
    apply_customer_schema(graph)
    session_id = str(uuid.uuid4())
    graph.query(
        """
        MERGE (c:Customer {id: $cid})
        MERGE (a:Agent {name: $agent})
        CREATE (s:Session {id: $sid, started_at: $ts})
        CREATE (c)-[:HAD_SESSION]->(s)
        CREATE (s)-[:HANDLED_BY]->(a)
        """,
        {"cid": customer_id, "agent": agent_name, "sid": session_id, "ts": _now()},
    )
    return session_id


def handoff_session(customer_id: str, from_session: str, to_agent: str) -> str:
    """Hand this customer from one agent persona to another.

    The new session is chained to the previous one with :NEXT. Nothing is
    copied: the receiving agent is a separate process with an empty context
    window, and it recovers everything by traversing this chain. That is the
    coordination claim, and it is only true because the graph is the memory.
    """
    graph = get_customer_graph(customer_id)
    new_session_id = str(uuid.uuid4())
    result = graph.query(
        """
        MATCH (prev:Session {id: $prev_id}), (c:Customer {id: $cid})
        MERGE (a:Agent {name: $agent})
        CREATE (next:Session {id: $next_id, started_at: $ts})
        CREATE (prev)-[:NEXT]->(next)
        CREATE (next)-[:HANDLED_BY]->(a)
        CREATE (c)-[:HAD_SESSION]->(next)
        RETURN next.id
        """,
        {
            "prev_id": from_session,
            "cid": customer_id,
            "agent": to_agent,
            "next_id": new_session_id,
            "ts": _now(),
        },
    )
    if not result.result_set:
        raise ValueError(
            f"cannot hand off: session {from_session} not found for customer {customer_id}"
        )
    return new_session_id


def recall_customer_context(customer_id: str) -> dict:
    """Episodic plus semantic recall for one customer.

    Returns every session in chronological order with the agent that handled
    it, every known fact with the agent that learned it, and every past issue.
    An agent calls this before it says anything; without it the agent knows
    nothing, which is exactly the dependency the hackathon asks us to prove.
    """
    graph = get_customer_graph(customer_id)

    sessions = graph.query(
        """
        MATCH (c:Customer {id: $cid})-[:HAD_SESSION]->(s:Session)-[:HANDLED_BY]->(a:Agent)
        RETURN s.id, s.started_at, a.name
        ORDER BY s.started_at
        """,
        {"cid": customer_id},
    ).result_set

    facts = graph.query(
        """
        MATCH (c:Customer {id: $cid})-[:HAS_FACT]->(f:Fact)
        OPTIONAL MATCH (s:Session)-[:LEARNED]->(f)
        OPTIONAL MATCH (s)-[:HANDLED_BY]->(a:Agent)
        RETURN f.key, f.value, collect(DISTINCT a.name)
        """,
        {"cid": customer_id},
    ).result_set

    issues = graph.query(
        """
        MATCH (c:Customer {id: $cid})-[:HAD_SESSION]->(s:Session)-[:RAISED]->(i:Issue)
        RETURN i.type, i.resolved_with, s.started_at
        ORDER BY s.started_at
        """,
        {"cid": customer_id},
    ).result_set

    return {
        "customer_id": customer_id,
        "sessions": [
            {"id": r[0], "started_at": r[1], "handled_by": r[2]} for r in sessions
        ],
        "facts": [
            {"key": r[0], "value": r[1], "learned_by": r[2] or []} for r in facts
        ],
        "past_issues": [
            {"type": r[0], "resolved_with": r[1], "occurred_at": r[2]} for r in issues
        ],
    }


def record_fact(customer_id: str, session_id: str, key: str, value: str) -> dict:
    """Semantic memory write, with provenance back to the session that learned it.

    MERGE on the Fact means re-learning the same key updates it rather than
    duplicating it, so a customer never ends up with two conflicting 'plan'
    facts. The :LEARNED edge is what lets the UI show which agent found it.
    """
    graph = get_customer_graph(customer_id)
    graph.query(
        """
        MATCH (c:Customer {id: $cid}), (s:Session {id: $sid})
        MERGE (c)-[:HAS_FACT]->(f:Fact {key: $key})
        SET f.value = $value, f.updated_at = $ts
        MERGE (s)-[:LEARNED]->(f)
        """,
        {
            "cid": customer_id,
            "sid": session_id,
            "key": key,
            "value": value,
            "ts": _now(),
        },
    )
    return {"recorded": {"key": key, "value": value}}


def log_resolution(
    customer_id: str, session_id: str, issue_type: str, resolution_text: str
) -> dict:
    """Write an outcome to two places, deliberately.

    The Issue goes in the customer's own graph, because 'what happened to
    this customer' must stay inside their tenant boundary. The Resolution
    goes in the shared graph, because 'what fixes this class of problem' is
    the knowledge we want every other agent to inherit.
    """
    customer = get_customer_graph(customer_id)
    customer.query(
        """
        MATCH (s:Session {id: $sid})
        CREATE (i:Issue {id: $iid, type: $itype, resolved_with: $text, resolved_at: $ts})
        CREATE (s)-[:RAISED]->(i)
        """,
        {
            "sid": session_id,
            "iid": str(uuid.uuid4()),
            "itype": issue_type,
            "text": resolution_text,
            "ts": _now(),
        },
    )

    shared = get_shared_graph()
    apply_shared_schema(shared)
    shared.query(
        """
        MERGE (t:IssueType {name: $itype})
        CREATE (r:Resolution {
            id: $rid, text: $text, reuse_count: 0,
            source_customer: $cid, created_at: $ts
        })
        CREATE (r)-[:APPLIES_TO]->(t)
        """,
        {
            "itype": issue_type,
            "rid": str(uuid.uuid4()),
            "text": resolution_text,
            "cid": customer_id,
            "ts": _now(),
        },
    )
    return {"logged": {"issue_type": issue_type, "shared_with_all_agents": True}}


def find_similar_resolutions(issue_type: str) -> list[dict]:
    """Procedural recall across tenants: how has anyone ever fixed this?

    The reuse_count increment is a single Cypher SET, which FalkorDB applies
    atomically per query, so concurrent agents retrieving the same resolution
    cannot lose an increment. scripts/concurrency_test.py proves that.
    """
    shared = get_shared_graph()
    apply_shared_schema(shared)
    shared.query(
        """
        MATCH (r:Resolution)-[:APPLIES_TO]->(:IssueType {name: $itype})
        SET r.reuse_count = r.reuse_count + 1
        """,
        {"itype": issue_type},
    )
    rows = shared.query(
        """
        MATCH (r:Resolution)-[:APPLIES_TO]->(:IssueType {name: $itype})
        RETURN r.text, r.reuse_count, r.source_customer, r.created_at
        ORDER BY r.reuse_count DESC, r.created_at DESC
        """,
        {"itype": issue_type},
    ).result_set
    return [
        {
            "resolution_text": r[0],
            "reuse_count": r[1],
            "learned_while_helping": r[2],
            "created_at": r[3],
        }
        for r in rows
    ]


def known_issue_types() -> list[str]:
    """Every issue type the shared knowledge graph has ever seen."""
    shared = get_shared_graph()
    apply_shared_schema(shared)
    rows = shared.query(
        "MATCH (t:IssueType) RETURN t.name ORDER BY t.name"
    ).result_set
    return [r[0] for r in rows]


def graph_snapshot(customer_id: str) -> dict:
    """Nodes and edges of one customer's memory graph, for the UI panel."""
    graph = get_customer_graph(customer_id)
    node_rows = graph.query("MATCH (n) RETURN n").result_set
    edge_rows = graph.query(
        "MATCH (a)-[r]->(b) RETURN id(a), type(r), id(b)"
    ).result_set

    nodes = []
    for (node,) in node_rows:
        label = node.labels[0] if node.labels else "Node"
        props = dict(node.properties)
        nodes.append(
            {
                "id": node.id,
                "label": label,
                "caption": _caption(label, props),
                "properties": props,
            }
        )
    edges = [{"source": r[0], "type": r[1], "target": r[2]} for r in edge_rows]
    return {"nodes": nodes, "edges": edges}


def _caption(label: str, props: dict) -> str:
    """Shortest human-readable handle for a node, per label."""
    if label == "Customer":
        return props.get("id", "customer")
    if label == "Agent":
        return props.get("name", "agent")
    if label == "Fact":
        return f"{props.get('key')}: {props.get('value')}"
    if label == "Issue":
        return props.get("type", "issue")
    if label == "Session":
        return f"session {str(props.get('id', ''))[:8]}"
    if label == "IssueType":
        return props.get("name", "issue type")
    if label == "Resolution":
        return str(props.get("text", ""))[:40]
    return label
