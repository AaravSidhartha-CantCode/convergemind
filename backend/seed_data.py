"""Synthetic demo history. Entirely fabricated, per the hackathon's data rule.

Seeding matters for the demo: an agent that greets a brand new customer
proves nothing, whereas an agent that opens with 'I see you're on Pro and
emailed us about a duplicate charge in March' proves the memory works.
"""

from backend.memory_tools import log_resolution, record_fact, start_session

SEED_CUSTOMERS = [
    {
        "id": "cust_alice",
        "history_agent": "EmailAgent",
        "facts": {
            "name": "Alice Nwosu",
            "plan": "Pro",
            "preferred_channel": "email",
            "timezone": "Europe/London",
        },
        "issue_type": "billing_mismatch",
        "resolution": "Refunded the duplicate March charge and waived the late fee.",
    },
    {
        "id": "cust_bob",
        "history_agent": "ChatAgent",
        "facts": {
            "name": "Bob Tan",
            "plan": "Free",
            "preferred_channel": "chat",
            "known_blocker": "cannot receive SMS codes abroad",
        },
        "issue_type": "password_reset",
        "resolution": "Recommended an email reset link instead of SMS, with identity verification by security question.",
    },
    {
        "id": "cust_carol",
        "history_agent": "EmailAgent",
        "facts": {
            "name": "Carol Mendes",
            "plan": "Enterprise",
            "preferred_channel": "chat",
            "account_note": "has a dedicated success manager",
        },
        "issue_type": "billing_mismatch",
        "resolution": "Applied a prorated credit for the 4 hours of downtime in the invoice period.",
    },
    {
        "id": "cust_dan",
        "history_agent": "ChatAgent",
        "facts": {
            "name": "Dan Okafor",
            "plan": "Pro",
            "preferred_channel": "email",
        },
        "issue_type": "data_export_failure",
        "resolution": "Rebuilt the export job after clearing a stale lock on the workspace.",
    },
]


def seed_all() -> list[str]:
    """Idempotent enough for a demo: re-running adds another historic session."""
    seeded = []
    for customer in SEED_CUSTOMERS:
        session_id = start_session(customer["id"], agent_name=customer["history_agent"])
        for key, value in customer["facts"].items():
            record_fact(customer["id"], session_id, key=key, value=value)
        log_resolution(
            customer["id"],
            session_id,
            issue_type=customer["issue_type"],
            resolution_text=customer["resolution"],
        )
        seeded.append(customer["id"])
    return seeded


if __name__ == "__main__":
    seeded = seed_all()
    print(f"Seeded {len(seeded)} synthetic customers: {', '.join(seeded)}")
