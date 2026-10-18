from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)


def test_health_lists_personas():
    response = client.get("/health")
    assert response.status_code == 200
    assert set(response.json()["personas"]) == {
        "ChatAgent",
        "EmailAgent",
        "MemoryGuardian",
    }


def test_start_session_then_timeline(tenant):
    start = client.post(
        "/session/start", json={"customer_id": tenant, "agent_name": "ChatAgent"}
    )
    assert start.status_code == 200
    assert start.json()["session_id"]

    timeline = client.get(f"/customer/{tenant}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.json()["sessions"]) == 1


def test_unknown_persona_is_rejected(tenant):
    response = client.post(
        "/session/start", json={"customer_id": tenant, "agent_name": "VoiceAgent"}
    )
    assert response.status_code == 400


def test_guardian_cannot_be_used_as_a_support_handoff(tenant):
    first = client.post(
        "/session/start", json={"customer_id": tenant, "agent_name": "ChatAgent"}
    ).json()["session_id"]
    response = client.post(
        "/session/handoff",
        json={
            "customer_id": tenant,
            "from_session": first,
            "to_agent": "MemoryGuardian",
        },
    )
    assert response.status_code == 400


def test_handoff_endpoint_chains_sessions(tenant):
    first = client.post(
        "/session/start", json={"customer_id": tenant, "agent_name": "ChatAgent"}
    ).json()["session_id"]

    response = client.post(
        "/session/handoff",
        json={"customer_id": tenant, "from_session": first, "to_agent": "EmailAgent"},
    )
    assert response.status_code == 200
    timeline = client.get(f"/customer/{tenant}/timeline").json()
    assert timeline["sessions"][-1]["handled_by"] == "EmailAgent"


def test_handoff_with_bad_session_is_404(tenant):
    client.post("/session/start", json={"customer_id": tenant, "agent_name": "ChatAgent"})
    response = client.post(
        "/session/handoff",
        json={"customer_id": tenant, "from_session": "nope", "to_agent": "EmailAgent"},
    )
    assert response.status_code == 404


@patch("backend.api.run_agent_turn", return_value={"reply": "mocked", "tool_trace": []})
def test_message_endpoint_delegates_to_agent(mock_run, tenant):
    session_id = client.post(
        "/session/start", json={"customer_id": tenant, "agent_name": "ChatAgent"}
    ).json()["session_id"]

    response = client.post(
        "/message",
        json={
            "customer_id": tenant,
            "session_id": session_id,
            "agent_name": "ChatAgent",
            "message": "hi",
        },
    )
    assert response.status_code == 200
    assert response.json()["reply"] == "mocked"
    mock_run.assert_called_once_with(tenant, session_id, "ChatAgent", "hi")


def test_graph_endpoint_returns_nodes(tenant):
    client.post("/session/start", json={"customer_id": tenant, "agent_name": "ChatAgent"})
    response = client.get(f"/customer/{tenant}/graph")
    assert response.status_code == 200
    assert response.json()["nodes"]


def test_customers_endpoint_lists_tenants(tenant):
    client.post("/session/start", json={"customer_id": tenant, "agent_name": "ChatAgent"})
    response = client.get("/customers")
    assert tenant in response.json()["customers"]
