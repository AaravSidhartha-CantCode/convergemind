"""Agent wiring. The model is mocked: this tests dispatch, not model quality."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.agent import PERSONAS, TOOL_SCHEMAS, _dispatch_for, run_agent_turn


def _tool_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def _completion(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_every_advertised_tool_has_an_implementation():
    advertised = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    implemented = set(_dispatch_for("cust_x", "sess_x"))
    assert advertised == implemented


def test_no_tool_schema_exposes_customer_id():
    """Tenant binding is server-side; the model must not be able to name a tenant."""
    for schema in TOOL_SCHEMAS:
        properties = schema["function"]["parameters"]["properties"]
        assert "customer_id" not in properties
        assert "session_id" not in properties


def test_both_personas_mandate_recall_first():
    for prompt in PERSONAS.values():
        assert "recall_customer_context FIRST" in prompt


@patch("backend.agent._get_client")
def test_run_agent_turn_executes_tools_then_returns_reply(mock_get_client, tenant):
    from backend.memory_tools import start_session

    session_id = start_session(tenant, agent_name="ChatAgent")

    first = _completion(
        SimpleNamespace(
            content="",
            tool_calls=[_tool_call("recall_customer_context", {})],
        )
    )
    second = _completion(
        SimpleNamespace(content="Hi, I can see your history.", tool_calls=None)
    )
    client = MagicMock()
    client.chat.completions.create.side_effect = [first, second]
    mock_get_client.return_value = client

    result = run_agent_turn(tenant, session_id, "ChatAgent", "hello")

    assert result["reply"] == "Hi, I can see your history."
    assert [entry["tool"] for entry in result["tool_trace"]] == [
        "recall_customer_context"
    ]
    assert result["tool_trace"][0]["result"]["customer_id"] == tenant


@patch("backend.agent._get_client")
def test_tool_errors_are_returned_to_the_model_not_raised(mock_get_client, tenant):
    from backend.memory_tools import start_session

    session_id = start_session(tenant, agent_name="ChatAgent")

    first = _completion(
        SimpleNamespace(
            content="",
            tool_calls=[_tool_call("record_fact", {"key": "plan"})],  # missing value
        )
    )
    second = _completion(SimpleNamespace(content="Sorry, retrying.", tool_calls=None))
    client = MagicMock()
    client.chat.completions.create.side_effect = [first, second]
    mock_get_client.return_value = client

    result = run_agent_turn(tenant, session_id, "ChatAgent", "hello")
    assert "error" in result["tool_trace"][0]["result"]
    assert result["reply"] == "Sorry, retrying."


@patch("backend.agent._get_client")
def test_tool_loop_is_bounded(mock_get_client, tenant):
    from backend.memory_tools import start_session

    session_id = start_session(tenant, agent_name="ChatAgent")

    looping = _completion(
        SimpleNamespace(
            content="", tool_calls=[_tool_call("known_issue_types", {})]
        )
    )
    client = MagicMock()
    client.chat.completions.create.return_value = looping
    mock_get_client.return_value = client

    result = run_agent_turn(tenant, session_id, "ChatAgent", "hello")
    assert "tool budget" in result["reply"]
    assert client.chat.completions.create.call_count == 6


def test_unknown_persona_is_rejected():
    with pytest.raises(ValueError):
        run_agent_turn("cust_x", "sess_x", "VoiceAgent", "hello")
