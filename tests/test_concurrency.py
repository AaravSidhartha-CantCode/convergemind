"""High-concurrency reads and writes, the Track 2 criterion that needs proof.

The claim: many agents serving many different customers hammer the shared
knowledge graph at once, and FalkorDB loses nothing. The counter is the
proof, because a lost update is immediately visible as a short count.
"""

import concurrent.futures
import uuid

from backend.db import get_customer_graph
from backend.memory_tools import (
    find_similar_resolutions,
    log_resolution,
    record_fact,
    recall_customer_context,
    start_session,
)

WORKERS = 12


def test_concurrent_retrievals_lose_no_increments(issue_type):
    """50 concurrent retrievals must produce exactly 50 increments."""
    seed_tenant = f"test_{uuid.uuid4().hex[:8]}"
    try:
        session_id = start_session(seed_tenant, agent_name="ChatAgent")
        log_resolution(
            seed_tenant,
            session_id,
            issue_type=issue_type,
            resolution_text="Baseline fix.",
        )

        retrievals = 50
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(
                pool.map(
                    lambda _: find_similar_resolutions(issue_type=issue_type),
                    range(retrievals),
                )
            )

        final = find_similar_resolutions(issue_type=issue_type)[0]["reuse_count"]
        # retrievals + the final verifying call
        assert final == retrievals + 1
    finally:
        get_customer_graph(seed_tenant).delete()


def test_concurrent_writes_across_tenants_stay_isolated():
    """30 tenants written in parallel: every one ends up with exactly its own fact."""
    tenants = [f"test_{uuid.uuid4().hex[:8]}" for _ in range(30)]
    try:

        def write_one(customer_id: str) -> None:
            session_id = start_session(customer_id, agent_name="ChatAgent")
            record_fact(customer_id, session_id, key="owner", value=customer_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(write_one, tenants))

        for customer_id in tenants:
            facts = recall_customer_context(customer_id)["facts"]
            assert len(facts) == 1
            assert facts[0]["value"] == customer_id
    finally:
        for customer_id in tenants:
            try:
                get_customer_graph(customer_id).delete()
            except Exception:
                pass
