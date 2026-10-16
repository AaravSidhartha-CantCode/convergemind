"""HTTP surface. Thin: every endpoint is a pass-through to a Cypher-backed tool."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.agent import PERSONAS, run_agent_turn
from backend.memory_tools import (
    find_similar_resolutions,
    graph_snapshot,
    handoff_session,
    known_issue_types,
    recall_customer_context,
    start_session,
)
from backend.db import list_customer_graphs

app = FastAPI(title="ConvergeMind", version="1.0.0")


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
    if req.to_agent not in PERSONAS:
        raise HTTPException(400, f"unknown agent persona: {req.to_agent}")
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


@app.get("/knowledge/issue-types")
def issue_types():
    return {"issue_types": known_issue_types()}


@app.get("/knowledge/resolutions/{issue_type}")
def resolutions(issue_type: str):
    return {"resolutions": find_similar_resolutions(issue_type)}
