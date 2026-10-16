"""Live concurrency demo. Run this on camera.

Two claims, both checked rather than asserted in prose:

  1. Many agents retrieving the same shared resolution at once lose no
     increments, because the increment is one atomic Cypher SET.
  2. Many agents writing to many different tenants at once never cross a
     tenant boundary, because each tenant is a separate FalkorDB graph key.

Usage:  python -m scripts.concurrency_test
"""

import concurrent.futures
import sys
import time
import uuid

from backend.db import get_customer_graph
from backend.memory_tools import (
    find_similar_resolutions,
    log_resolution,
    recall_customer_context,
    record_fact,
    start_session,
)

RETRIEVALS = 200
TENANTS = 100
WORKERS = 16


def _banner(text: str) -> None:
    print(f"\n{text}\n{'=' * len(text)}")


def prove_atomic_shared_writes() -> bool:
    _banner(f"1. {RETRIEVALS} concurrent retrievals of one shared resolution")
    issue_type = f"demo_{uuid.uuid4().hex[:8]}"
    seed_tenant = f"demo_seed_{uuid.uuid4().hex[:6]}"
    try:
        session_id = start_session(seed_tenant, agent_name="ChatAgent")
        log_resolution(
            seed_tenant,
            session_id,
            issue_type=issue_type,
            resolution_text="Baseline fix, retrieved by every agent at once.",
        )

        started = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(
                pool.map(
                    lambda _: find_similar_resolutions(issue_type=issue_type),
                    range(RETRIEVALS),
                )
            )
        elapsed = time.time() - started

        observed = find_similar_resolutions(issue_type=issue_type)[0]["reuse_count"]
        expected = RETRIEVALS + 1  # + the verifying read above
        ok = observed == expected

        print(f"   workers            : {WORKERS}")
        print(f"   elapsed            : {elapsed:.2f}s ({RETRIEVALS / elapsed:.0f} ops/s)")
        print(f"   reuse_count        : {observed}")
        print(f"   expected           : {expected}")
        print(f"   lost updates       : {expected - observed}")
        print(f"   -> {'PASS, no lost writes' if ok else 'FAIL, writes were lost'}")
        return ok
    finally:
        get_customer_graph(seed_tenant).delete()


def prove_tenant_isolation_under_load() -> bool:
    _banner(f"2. {TENANTS} tenants written concurrently, checked for bleed")
    tenants = [f"demo_t_{uuid.uuid4().hex[:8]}" for _ in range(TENANTS)]
    try:

        def write_one(customer_id: str) -> None:
            session_id = start_session(customer_id, agent_name="ChatAgent")
            record_fact(customer_id, session_id, key="owner", value=customer_id)

        started = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            list(pool.map(write_one, tenants))
        elapsed = time.time() - started

        bleed = 0
        for customer_id in tenants:
            facts = recall_customer_context(customer_id)["facts"]
            if len(facts) != 1 or facts[0]["value"] != customer_id:
                bleed += 1

        print(f"   workers            : {WORKERS}")
        print(f"   elapsed            : {elapsed:.2f}s ({TENANTS / elapsed:.0f} tenants/s)")
        print(f"   graph keys written : {TENANTS}")
        print(f"   cross-tenant bleed : {bleed}")
        print(f"   -> {'PASS, every tenant isolated' if bleed == 0 else 'FAIL, data crossed tenants'}")
        return bleed == 0
    finally:
        for customer_id in tenants:
            try:
                get_customer_graph(customer_id).delete()
            except Exception:
                pass


if __name__ == "__main__":
    print("ConvergeMind concurrency proof against FalkorDB")
    results = [prove_atomic_shared_writes(), prove_tenant_isolation_under_load()]
    _banner("RESULT")
    print("   ALL CHECKS PASSED" if all(results) else "   FAILURES PRESENT")
    sys.exit(0 if all(results) else 1)
