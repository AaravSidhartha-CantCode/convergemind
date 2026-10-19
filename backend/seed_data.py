"""Synthetic support history for the public demo.

The app uses ordinary account-support cases as an example workload. The
product itself is the governed memory layer beneath the agents, not a CRM.
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
        "resolution": "Recommended refunding the duplicate March charge and waiving the late fee.",
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
        "resolution": "Recommended a prorated credit for 4 hours of downtime in the invoice period.",
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
        "resolution": "Recommended rebuilding the export job after clearing a stale workspace lock.",
    },
]


def seed_all() -> list[str]:
    """Seed a small synthetic set. Re-running adds another history event."""
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
