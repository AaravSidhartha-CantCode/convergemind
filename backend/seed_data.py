"""Synthetic housing-recovery cases for the public demo.

These are invented examples. They make the coordination problem concrete
without exposing any real applicant, caseworker, or relief-provider data.
"""

from backend.memory_tools import log_resolution, record_fact, start_session

SEED_CUSTOMERS = [
    {
        "id": "cust_maya",
        "history_agent": "EmailAgent",
        "facts": {
            "name": "Maya Ortiz",
            "assistance_path": "housing recovery",
            "preferred_channel": "email — public library access",
            "known_blocker": "Lost phone after flooding; do not use SMS",
            "accessibility_need": "step-free temporary housing",
            "document_status": "photo ID uploaded; lease copy pending",
        },
        "issue_type": "temporary_housing",
        "resolution": (
            "Recommended a step-free temporary-housing intake through the city "
            "relief desk, with the document checklist confirmed by email."
        ),
    },
    {
        "id": "cust_amina",
        "history_agent": "ChatAgent",
        "facts": {
            "name": "Amina Nwosu",
            "assistance_path": "rental recovery",
            "preferred_channel": "email",
            "document_status": "landlord notice uploaded; income proof pending",
            "household_need": "two school-age children",
        },
        "issue_type": "document_follow_up",
        "resolution": (
            "Recommended a document checklist and a human caseworker review "
            "before any rental-assistance eligibility decision."
        ),
    },
    {
        "id": "cust_dev",
        "history_agent": "EmailAgent",
        "facts": {
            "name": "Dev Shah",
            "assistance_path": "housing recovery",
            "preferred_channel": "phone call through caseworker",
            "known_blocker": "limited internet access",
            "document_status": "identity documents verified",
        },
        "issue_type": "transportation_access",
        "resolution": (
            "Recommended a caseworker callback to coordinate transport options "
            "for an in-person housing-recovery appointment."
        ),
    },
    {
        "id": "cust_elena",
        "history_agent": "ChatAgent",
        "facts": {
            "name": "Elena Petrov",
            "assistance_path": "temporary housing",
            "preferred_channel": "email",
            "accessibility_need": "ground-floor placement preferred",
            "document_status": "intake form completed",
        },
        "issue_type": "temporary_housing",
        "resolution": (
            "Recommended an accessibility-aware placement review with a human "
            "housing coordinator before confirming a referral."
        ),
    },
]


def seed_all() -> list[str]:
    """Seed a small, synthetic case set. Re-running adds another history event."""
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
    print(f"Seeded {len(seeded)} synthetic assistance cases: {', '.join(seeded)}")
