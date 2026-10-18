"""The two agent personas.

ChatAgent and EmailAgent are separate invocations with separate context
windows. They never pass each other a transcript, a summary, or a cache.
Everything one knows about the other's work it learned by querying
FalkorDB through the tools below. Only verified graph claims are placed in
an agent's recall context; proposed, disputed, and quarantined memories are
visible to the Memory Guardian but cannot direct an agent action.

Tenant boundary note: the tool schemas handed to the model do NOT take a
customer_id. The server binds it from the current request (see
`_dispatch_for`), so the model cannot switch tenants through a tool call.
The HTTP API is a synthetic-data demo and has no user authentication:
external callers can choose a customer_id. Graph keys isolate database
queries; they do not authorize callers to access a tenant.
"""

import json
import os

from groq import Groq

from backend.memory_tools import (
    find_similar_resolutions,
    known_issue_types,
    log_resolution,
    recall_customer_context,
    record_fact,
)

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_TOOL_ROUNDS = 6

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=api_key)
    return _client


_SHARED_RULES = """
You are a customer support agent for a SaaS product, working inside a system
where your memory is a shared graph database rather than your own context.

Non-negotiable procedure:
1. Call recall_customer_context FIRST, before you say anything at all. You
   start every conversation with no memory, so this is the only way you know
   who you are talking to.
2. Never ask the customer for something recall_customer_context already told
   you. Reference it instead, naturally, so they can tell you remembered.
3. If the customer's problem resembles a known issue type, call
   find_similar_resolutions to see how it was fixed before, for anyone.
4. When you learn a durable fact about the customer (their plan, a
   preference, an account detail), call record_fact.
5. When you resolve something, call log_resolution so every other agent
   inherits the fix.

Be concise. Do not narrate your tool use to the customer.
""".strip()

PERSONAS = {
    "ChatAgent": _SHARED_RULES
    + "\n\nYou are on live chat. Write short, informal, fast replies. Two or three sentences at most.",
    "EmailAgent": _SHARED_RULES
    + "\n\nYou are writing an email reply. Use a brief greeting and a sign-off, and keep it under four sentences.",
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "recall_customer_context",
            "description": (
                "Retrieve everything known about the customer you are currently "
                "serving: every past session and which agent handled it, every "
                "known fact about them, and every past issue. Call this first, "
                "always. Takes no arguments."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_fact",
            "description": (
                "Store a durable fact about the current customer so that every "
                "future agent, on any channel, inherits it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Short snake_case fact name, e.g. plan, preferred_channel, timezone",
                    },
                    "value": {"type": "string", "description": "The fact's value"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_resolution",
            "description": (
                "Record how you resolved an issue. Writes the issue to this "
                "customer's history and the reusable fix to the shared "
                "knowledge graph that every other agent reads."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "description": "Short snake_case category, e.g. billing_mismatch, password_reset",
                    },
                    "resolution_text": {
                        "type": "string",
                        "description": "One sentence describing what fixed it",
                    },
                },
                "required": ["issue_type", "resolution_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_similar_resolutions",
            "description": (
                "Look up how this type of issue has been resolved before, for "
                "ANY customer, not just this one. This is shared procedural "
                "knowledge across the whole support team."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_type": {
                        "type": "string",
                        "description": "The issue category to search for",
                    }
                },
                "required": ["issue_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "known_issue_types",
            "description": (
                "List every issue type the shared knowledge graph has seen, to "
                "help you pick an existing category instead of inventing one."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def _dispatch_for(customer_id: str, session_id: str) -> dict:
    """Bind tools to this session's tenant. The model cannot override these."""
    return {
        "recall_customer_context": lambda **_: recall_customer_context(customer_id),
        "record_fact": lambda key, value, **_: record_fact(
            customer_id, session_id, key, value
        ),
        "log_resolution": lambda issue_type, resolution_text, **_: log_resolution(
            customer_id, session_id, issue_type, resolution_text
        ),
        "find_similar_resolutions": lambda issue_type, **_: find_similar_resolutions(
            issue_type
        ),
        "known_issue_types": lambda **_: known_issue_types(),
    }


def run_agent_turn(
    customer_id: str, session_id: str, agent_name: str, user_message: str
) -> dict:
    """One agent turn. Returns the reply plus the tool calls it made.

    The tool trace is returned, not hidden, because the demo's whole point is
    showing judges that the answer came out of the graph.
    """
    if agent_name not in PERSONAS:
        raise ValueError(f"unknown agent persona: {agent_name}")

    dispatch = _dispatch_for(customer_id, session_id)
    messages = [
        {"role": "system", "content": PERSONAS[agent_name]},
        {"role": "user", "content": user_message},
    ]
    trace = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            max_tokens=900,
            temperature=0.3,
        )
        message = response.choices[0].message

        if not message.tool_calls:
            return {"reply": message.content or "", "tool_trace": trace}

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in message.tool_calls
                ],
            }
        )

        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if name not in dispatch:
                result = {"error": f"unknown tool {name}"}
            else:
                try:
                    result = dispatch[name](**args)
                except Exception as exc:  # surfaced to the model so it can recover
                    result = {"error": str(exc)}
            trace.append({"tool": name, "arguments": args, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, default=str),
                }
            )

    return {
        "reply": "I could not finish that within my tool budget. Please rephrase.",
        "tool_trace": trace,
    }
