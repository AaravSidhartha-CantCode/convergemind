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

Memory immunity adds a governed layer on top of those durable facts:

  (Session)-[:ASSERTED]->(MemoryClaim)<-[:SUPPORTS]-(Evidence)
  (MemoryClaim)-[:CONTRADICTS|SUPERSEDES]->(MemoryClaim)
  (Decision)-[:DEPENDS_ON]->(MemoryClaim)-[:CAPTURED_IN]->(HandoffCapsule)

A claim can be proposed, verified, disputed, superseded, or quarantined.
When a verified claim supersedes an older one, dependent decisions and
handoff capsules are marked for revalidation instead of silently relying on
stale context.
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
    create_handoff_capsule(customer_id, from_session, new_session_id)
    return new_session_id


def create_handoff_capsule(customer_id: str, from_session: str, to_session: str) -> dict:
    """Build a small, evidence-backed handoff instead of copying a transcript.

    Only verified claims travel. Disputed and quarantined memories remain
    inspectable in the graph but cannot quietly steer the next agent.
    """
    graph = get_customer_graph(customer_id)
    capsule_id = str(uuid.uuid4())
    result = graph.query(
        """
        MATCH (from:Session {id: $from_session}), (to:Session {id: $to_session})
        CREATE (h:HandoffCapsule {
            id: $hid, status: 'current', created_at: $ts,
            summary: 'Verified context handoff; transcript intentionally excluded.'
        })
        CREATE (from)-[:HANDED_OFF]->(h)
        CREATE (h)-[:DELIVERED_TO]->(to)
        RETURN h.id
        """,
        {"from_session": from_session, "to_session": to_session, "hid": capsule_id, "ts": _now()},
    ).result_set
    graph.query(
        """
        MATCH (h:HandoffCapsule {id: $hid}), (m:MemoryClaim {status: 'verified'})
        CREATE (m)-[:CAPTURED_IN]->(h)
        """,
        {"hid": capsule_id},
    )
    count = graph.query(
        "MATCH (:HandoffCapsule {id: $hid})<-[:CAPTURED_IN]-(m:MemoryClaim) RETURN count(m)",
        {"hid": capsule_id},
    ).result_set
    return {"id": capsule_id, "verified_claim_count": count[0][0] if count else 0}


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

    claims = graph.query(
        """
        MATCH (c:Customer {id: $cid})-[:HAS_CLAIM]->(m:MemoryClaim {status: 'verified'})
        OPTIONAL MATCH (e:Evidence)-[:SUPPORTS]->(m)
        RETURN m.id, m.key, m.value, m.status, m.source_trust, m.source_type,
               collect(DISTINCT e.text)
        ORDER BY m.created_at DESC
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
        "claims": [
            {
                "id": r[0], "key": r[1], "value": r[2], "status": r[3],
                "source_trust": r[4], "source_type": r[5], "evidence": r[6] or [],
            }
            for r in claims
        ],
    }


def record_fact(customer_id: str, session_id: str, key: str, value: str) -> dict:
    """Semantic memory write, with provenance back to the session that learned it.

    MERGE on the Fact means re-learning the same key updates it rather than
    duplicating it, so a customer never ends up with two conflicting 'plan'
    facts. The :LEARNED edge is what lets the UI show which agent found it.
    """
    graph = get_customer_graph(customer_id)
    claim = write_memory_claim(
        customer_id,
        session_id,
        key=key,
        value=value,
        evidence_text="Direct observation recorded by the active agent session.",
        source_type="agent_session",
        source_trust=1.0,
        status="proposed",
    )
    verification = verify_memory_claim(customer_id, claim["id"])
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
    claim["status"] = "verified"
    return {
        "recorded": {"key": key, "value": value},
        "claim": claim,
        "blast_radius": verification["blast_radius"],
    }


VALID_CLAIM_STATUSES = {"proposed", "verified", "disputed", "superseded", "quarantined"}


def write_memory_claim(
    customer_id: str,
    session_id: str,
    key: str,
    value: str,
    evidence_text: str,
    source_type: str = "external",
    source_trust: float = 0.5,
    status: str = "proposed",
) -> dict:
    """Create an evidence-backed memory claim without making it agent truth.

    Agent memories are claims, not an append-only pile of facts. Untrusted
    external material is quarantined before it can enter an agent handoff.
    """
    if status not in VALID_CLAIM_STATUSES:
        raise ValueError(f"unknown claim status: {status}")
    if not 0 <= source_trust <= 1:
        raise ValueError("source_trust must be between 0 and 1")
    if source_type == "external" and source_trust < 0.6 and status == "proposed":
        status = "quarantined"

    graph = get_customer_graph(customer_id)
    apply_customer_schema(graph)
    claim_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())
    graph.query(
        """
        MATCH (c:Customer {id: $cid}), (s:Session {id: $sid})
        CREATE (m:MemoryClaim {
            id: $mid, key: $key, value: $value, status: $status,
            source_trust: $trust, source_type: $source_type, created_at: $ts
        })
        CREATE (e:Evidence {
            id: $eid, text: $evidence, source_type: $source_type,
            trust: $trust, created_at: $ts
        })
        CREATE (c)-[:HAS_CLAIM]->(m)
        CREATE (s)-[:ASSERTED]->(m)
        CREATE (e)-[:SUPPORTS]->(m)
        """,
        {
            "cid": customer_id,
            "sid": session_id,
            "mid": claim_id,
            "eid": evidence_id,
            "key": key,
            "value": value,
            "status": status,
            "trust": source_trust,
            "source_type": source_type,
            "evidence": evidence_text,
            "ts": _now(),
        },
    )
    return {
        "id": claim_id,
        "key": key,
        "value": value,
        "status": status,
        "source_trust": source_trust,
    }


def verify_memory_claim(customer_id: str, claim_id: str) -> dict:
    """Verify a claim and surface every decision or handoff it invalidates."""
    graph = get_customer_graph(customer_id)
    target = graph.query(
        """
        MATCH (c:Customer {id: $cid})-[:HAS_CLAIM]->(m:MemoryClaim {id: $mid})
        RETURN m.key, m.value, m.status
        """,
        {"cid": customer_id, "mid": claim_id},
    ).result_set
    if not target:
        raise ValueError(f"claim {claim_id} not found for customer {customer_id}")

    key, value, _ = target[0]
    graph.query(
        "MATCH (m:MemoryClaim {id: $mid}) SET m.status = 'verified', m.verified_at = $ts",
        {"mid": claim_id, "ts": _now()},
    )
    # Keep the legacy semantic Fact projection aligned with the governed
    # claim. Agents still receive facts for concise recall, so leaving the
    # projection stale would reintroduce the very contradiction the Guardian
    # is meant to prevent.
    graph.query(
        """
        MATCH (c:Customer {id: $cid})-[:HAS_CLAIM]->(:MemoryClaim {id: $mid})
        MERGE (c)-[:HAS_FACT]->(f:Fact {key: $key})
        SET f.value = $value, f.updated_at = $ts
        """,
        {"cid": customer_id, "mid": claim_id, "key": key, "value": value, "ts": _now()},
    )
    superseded = graph.query(
        """
        MATCH (old:MemoryClaim {key: $key, status: 'verified'})
        WHERE old.id <> $mid AND old.value <> $value
        MATCH (current:MemoryClaim {id: $mid})
        SET old.status = 'superseded', old.superseded_at = $ts
        MERGE (current)-[:SUPERSEDES]->(old)
        RETURN old.id
        """,
        {"key": key, "mid": claim_id, "value": value, "ts": _now()},
    ).result_set

    decision_rows = graph.query(
        """
        MATCH (current:MemoryClaim {id: $mid})-[:SUPERSEDES]->(old:MemoryClaim)
              <-[:DEPENDS_ON]-(d:Decision)
        SET d.status = 'needs_revalidation', d.invalidated_at = $ts
        RETURN d.id, d.text
        """,
        {"mid": claim_id, "ts": _now()},
    ).result_set
    handoff_rows = graph.query(
        """
        MATCH (current:MemoryClaim {id: $mid})-[:SUPERSEDES]->(old:MemoryClaim)
              -[:CAPTURED_IN]->(h:HandoffCapsule)
        SET h.status = 'needs_revalidation', h.invalidated_at = $ts
        RETURN h.id
        """,
        {"mid": claim_id, "ts": _now()},
    ).result_set
    return {
        "verified_claim": claim_id,
        "superseded_claim_ids": [row[0] for row in superseded],
        "blast_radius": {
            "decisions": [{"id": row[0], "text": row[1]} for row in decision_rows],
            "handoff_capsule_ids": [row[0] for row in handoff_rows],
        },
    }


def relate_claims(customer_id: str, claim_id: str, other_claim_id: str, relation: str) -> None:
    """Record an explicit contradiction or supersession between two claims."""
    if relation not in {"CONTRADICTS", "SUPERSEDES"}:
        raise ValueError("relation must be CONTRADICTS or SUPERSEDES")
    graph = get_customer_graph(customer_id)
    result = graph.query(
        f"""
        MATCH (:Customer {{id: $cid}})-[:HAS_CLAIM]->(a:MemoryClaim {{id: $claim_id}})
        MATCH (:Customer {{id: $cid}})-[:HAS_CLAIM]->(b:MemoryClaim {{id: $other_id}})
        MERGE (a)-[:{relation}]->(b)
        SET a.status = CASE WHEN $relation = 'CONTRADICTS' THEN 'disputed' ELSE a.status END,
            b.status = CASE WHEN $relation = 'CONTRADICTS' THEN 'disputed' ELSE b.status END
        RETURN a.id
        """,
        {"cid": customer_id, "claim_id": claim_id, "other_id": other_claim_id, "relation": relation},
    ).result_set
    if not result:
        raise ValueError("both claims must exist in the selected customer graph")


def quarantine_memory_claim(customer_id: str, claim_id: str, reason: str) -> dict:
    """Keep suspicious memory for audit while excluding it from agent context."""
    graph = get_customer_graph(customer_id)
    result = graph.query(
        """
        MATCH (:Customer {id: $cid})-[:HAS_CLAIM]->(m:MemoryClaim {id: $mid})
        SET m.status = 'quarantined', m.quarantine_reason = $reason,
            m.quarantined_at = $ts
        RETURN m.id
        """,
        {"cid": customer_id, "mid": claim_id, "reason": reason, "ts": _now()},
    ).result_set
    if not result:
        raise ValueError(f"claim {claim_id} not found for customer {customer_id}")
    return {"quarantined_claim": claim_id, "reason": reason}


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
    decision_id = str(uuid.uuid4())
    customer.query(
        """
        MATCH (s:Session {id: $sid})
        CREATE (d:Decision {
            id: $did, text: $text, status: 'current', created_at: $ts,
            kind: 'resolution'
        })
        CREATE (s)-[:MADE_DECISION]->(d)
        """,
        {"sid": session_id, "did": decision_id, "text": resolution_text, "ts": _now()},
    )
    customer.query(
        """
        MATCH (d:Decision {id: $did}), (m:MemoryClaim {status: 'verified'})
        CREATE (d)-[:DEPENDS_ON]->(m)
        """,
        {"did": decision_id},
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
    return {
        "logged": {"issue_type": issue_type, "shared_with_all_agents": True},
        "decision_id": decision_id,
    }


def memory_health(customer_id: str) -> dict:
    """Operational view for the Memory Guardian rail and judge-facing demo."""
    graph = get_customer_graph(customer_id)
    claims = graph.query(
        """
        MATCH (:Customer {id: $cid})-[:HAS_CLAIM]->(m:MemoryClaim)
        RETURN m.id, m.key, m.value, m.status, m.source_trust, m.source_type,
               m.quarantine_reason
        ORDER BY m.created_at DESC
        """,
        {"cid": customer_id},
    ).result_set
    conflicts = graph.query(
        """
        MATCH (a:MemoryClaim)-[:CONTRADICTS]->(b:MemoryClaim)
        RETURN a.id, b.id, a.key, a.value, b.value
        """
    ).result_set
    decisions = graph.query(
        """
        MATCH (d:Decision {status: 'needs_revalidation'})
        RETURN d.id, d.text, d.invalidated_at
        ORDER BY d.invalidated_at DESC
        """
    ).result_set
    handoffs = graph.query(
        """
        MATCH (h:HandoffCapsule {status: 'needs_revalidation'})
        RETURN h.id, h.invalidated_at
        ORDER BY h.invalidated_at DESC
        """
    ).result_set
    return {
        "claims": [
            {"id": r[0], "key": r[1], "value": r[2], "status": r[3],
             "source_trust": r[4], "source_type": r[5], "quarantine_reason": r[6]}
            for r in claims
        ],
        "conflicts": [
            {"claim_id": r[0], "other_claim_id": r[1], "key": r[2],
             "value": r[3], "other_value": r[4]}
            for r in conflicts
        ],
        "needs_revalidation": {
            "decisions": [{"id": r[0], "text": r[1], "invalidated_at": r[2]} for r in decisions],
            "handoffs": [{"id": r[0], "invalidated_at": r[1]} for r in handoffs],
        },
    }


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
    if label == "MemoryClaim":
        return f"{props.get('key')}: {props.get('value')} [{props.get('status')}]"
    if label == "Evidence":
        return str(props.get("text", "evidence"))[:34]
    if label == "Decision":
        return str(props.get("text", "decision"))[:34]
    if label == "HandoffCapsule":
        return f"handoff [{props.get('status', 'current')}]"
    if label == "Session":
        return f"session {str(props.get('id', ''))[:8]}"
    if label == "IssueType":
        return props.get("name", "issue type")
    if label == "Resolution":
        return str(props.get("text", ""))[:40]
    return label
