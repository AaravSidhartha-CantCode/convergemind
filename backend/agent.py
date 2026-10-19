"""The three agent personas.

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
    memory_health,
    quarantine_memory_claim,
    recall_customer_context,
    relate_claims,
    record_fact,
    verify_memory_claim,
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
6. You can recommend a next step and record that recommendation, but you
   cannot send email, reset an account, change a subscription, or perform any
   other external action. Never claim that you completed one of those actions.

Be concise. Do not narrate your tool use to the customer.
""".strip()

_GUARDIAN_RULES = """
You are MemoryGuardian, a governance agent for a customer-memory graph.
You do not provide customer support or invent customer facts. Your job is to
inspect evidence and keep unsafe or stale memories from directing the support
agents.

Non-negotiable procedure:
1. Call inspect_memory_health FIRST. It lists claims, their evidence and
   trust, and decisions or handoffs that need revalidation.
2. Verify a proposed claim only when its evidence and source trust support
   it. Explain the evidence you relied on and report the returned blast radius.
3. Quarantine a claim when its source is untrusted, its evidence is missing,
   or it could cause unsafe customer action. Give a concise reason.
4. If two claims conflict, record an explicit CONTRADICTS or SUPERSEDES
   relationship instead of silently choosing one.
5. Never call support-agent tools and never say a claim is true unless it has
   been verified in the graph.

Write a short audit-style response that names the claim status and the next
safe action.
""".strip()

PERSONAS = {
    "ChatAgent": _SHARED_RULES
    + "\n\nYou are on live chat. Write short, informal, fast replies. Two or three sentences at most.",
    "EmailAgent": _SHARED_RULES
    + "\n\nYou are writing an email reply. Use a brief greeting and a sign-off, and keep it under four sentences.",
    "MemoryGuardian": _GUARDIAN_RULES,
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
                "Record the recommended resolution for an issue. Writes the issue to this "
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
                        "description": "One sentence describing the recommended fix, without claiming it was executed",
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

GUARDIAN_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "inspect_memory_health",
            "description": "List the current customer's claims, evidence, statuses, and stale downstream decisions. Call this first. Takes no arguments.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verify_memory_claim",
            "description": "Verify one proposed claim after inspecting its evidence. Returns every affected decision and handoff capsule.",
            "parameters": {
                "type": "object",
                "properties": {"claim_id": {"type": "string", "description": "ID of the claim to verify"}},
                "required": ["claim_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "quarantine_memory_claim",
            "description": "Quarantine an unsafe or unsupported claim so support agents and handoffs cannot use it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "description": "ID of the claim to quarantine"},
                    "reason": {"type": "string", "description": "Short audit reason"},
                },
                "required": ["claim_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "relate_memory_claims",
            "description": "Make a conflict or supersession relationship explicit between two claims after inspecting them.",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string", "description": "First claim ID"},
                    "other_claim_id": {"type": "string", "description": "Second claim ID"},
                    "relation": {"type": "string", "enum": ["CONTRADICTS", "SUPERSEDES"]},
                },
                "required": ["claim_id", "other_claim_id", "relation"],
            },
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
        "inspect_memory_health": lambda **_: memory_health(customer_id),
        "verify_memory_claim": lambda claim_id, **_: verify_memory_claim(
            customer_id, claim_id
        ),
        "quarantine_memory_claim": lambda claim_id, reason, **_: quarantine_memory_claim(
            customer_id, claim_id, reason
        ),
        "relate_memory_claims": lambda claim_id, other_claim_id, relation, **_: relate_claims(
            customer_id, claim_id, other_claim_id, relation
        ),
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
    tool_schemas = (
        GUARDIAN_TOOL_SCHEMAS if agent_name == "MemoryGuardian" else TOOL_SCHEMAS
    )
    messages = [
        {"role": "system", "content": PERSONAS[agent_name]},
        {"role": "user", "content": user_message},
    ]
    trace = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = _get_client().chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tool_schemas,
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
