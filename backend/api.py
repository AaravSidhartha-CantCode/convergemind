"""HTTP surface. Thin: every endpoint is a pass-through to a Cypher-backed tool."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.agent import PERSONAS, run_agent_turn
from backend.memory_tools import (
    memory_health,
    quarantine_memory_claim,
    relate_claims,
    verify_memory_claim,
    write_memory_claim,
    find_similar_resolutions,
    graph_snapshot,
    handoff_session,
    known_issue_types,
    recall_customer_context,
    start_session,
)
from backend.db import list_customer_graphs

app = FastAPI(title="ConvergeMind", version="1.0.0")
SUPPORT_AGENT_NAMES = {"ChatAgent", "EmailAgent"}


class StartSessionRequest(BaseModel):
    customer_id: str
    agent_name: str


class HandoffRequest(BaseModel):
    customer_id: str
    from_session: str
    to_agent: str


class MessageRequest(BaseModel):
    customer_id: str
    session_id: str
    agent_name: str
    message: str


class MemoryClaimRequest(BaseModel):
    customer_id: str
    session_id: str
    key: str
    value: str
    evidence_text: str
    source_type: str = "external"
    source_trust: float = 0.5
    status: str = "proposed"


class ClaimRelationRequest(BaseModel):
    customer_id: str
    other_claim_id: str
    relation: str = "CONTRADICTS"


class QuarantineRequest(BaseModel):
    customer_id: str
    reason: str


@app.get("/health")
def health():
    return {"status": "ok", "personas": list(PERSONAS)}


@app.get("/customers")
def customers():
    """Tenants that exist, derived from FalkorDB graph keys."""
    return {
        "customers": [key.split("customer:", 1)[1] for key in list_customer_graphs()]
    }


@app.post("/session/start")
def session_start(req: StartSessionRequest):
    if req.agent_name not in PERSONAS:
        raise HTTPException(400, f"unknown agent persona: {req.agent_name}")
    return {"session_id": start_session(req.customer_id, req.agent_name)}


@app.post("/session/handoff")
def session_handoff(req: HandoffRequest):
    if req.to_agent not in SUPPORT_AGENT_NAMES:
        raise HTTPException(400, "handoffs are limited to ChatAgent and EmailAgent")
    try:
        session_id = handoff_session(req.customer_id, req.from_session, req.to_agent)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return {"session_id": session_id}


@app.post("/message")
def message(req: MessageRequest):
    if req.agent_name not in PERSONAS:
        raise HTTPException(400, f"unknown agent persona: {req.agent_name}")
    return run_agent_turn(
        req.customer_id, req.session_id, req.agent_name, req.message
    )


@app.get("/customer/{customer_id}/timeline")
def timeline(customer_id: str):
    return recall_customer_context(customer_id)


@app.get("/customer/{customer_id}/graph")
def customer_graph(customer_id: str):
    return graph_snapshot(customer_id)


@app.get("/customer/{customer_id}/memory-health")
def customer_memory_health(customer_id: str):
    """Memory Guardian view: trusted, disputed, and stale operational context."""
    return memory_health(customer_id)


@app.post("/memory/claim")
def create_memory_claim(req: MemoryClaimRequest):
    try:
        return write_memory_claim(
            req.customer_id,
            req.session_id,
            req.key,
            req.value,
            req.evidence_text,
            req.source_type,
            req.source_trust,
            req.status,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/memory/claim/{claim_id}/verify")
def verify_claim(claim_id: str, customer_id: str):
    try:
        return verify_memory_claim(customer_id, claim_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.post("/memory/claim/{claim_id}/relation")
def relate_memory_claim(claim_id: str, req: ClaimRelationRequest):
    try:
        relate_claims(req.customer_id, claim_id, req.other_claim_id, req.relation)
        return {"related": True, "relation": req.relation}
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@app.post("/memory/claim/{claim_id}/quarantine")
def quarantine_claim(claim_id: str, req: QuarantineRequest):
    try:
        return quarantine_memory_claim(req.customer_id, claim_id, req.reason)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.get("/knowledge/issue-types")
def issue_types():
    return {"issue_types": known_issue_types()}


@app.get("/knowledge/resolutions/{issue_type}")
def resolutions(issue_type: str):
    return {"resolutions": find_similar_resolutions(issue_type)}
