"""FalkorDB connection and tenant-isolation boundary.

Every customer gets their own FalkorDB graph key. That is the isolation
mechanism: not a WHERE clause an agent could forget, but a separate
keyspace a query physically cannot traverse out of. Cross-customer
knowledge is deliberately placed in one shared graph instead, so the
only data that crosses a tenant boundary is data we explicitly put there.
"""

import os
import threading

from falkordb import FalkorDB

_client = None
_client_lock = threading.Lock()

SHARED_GRAPH_KEY = "shared:knowledge"


def _get_client() -> FalkorDB:
    """One client, built once, shared by every thread.

    The double-checked lock matters because this project advertises
    high-concurrency reads and writes: without it, the first burst of
    parallel requests can each see `_client is None` and build their own
    client, quietly multiplying connection pools. The underlying redis
    client is itself thread-safe, so sharing one is the correct end state.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = FalkorDB(
                    host=os.environ.get("FALKORDB_HOST", "localhost"),
                    port=int(os.environ.get("FALKORDB_PORT", "6379")),
                    password=os.environ.get("FALKORDB_PASSWORD") or None,
                )
    return _client


def customer_graph_key(customer_id: str) -> str:
    return f"customer:{customer_id}"


def get_customer_graph(customer_id: str):
    """This customer's private memory. One graph key per tenant."""
    return _get_client().select_graph(customer_graph_key(customer_id))


def get_shared_graph():
    """Cross-customer procedural knowledge: IssueType and Resolution nodes."""
    return _get_client().select_graph(SHARED_GRAPH_KEY)


def list_customer_graphs() -> list[str]:
    """Every tenant keyspace that currently exists, for the demo UI."""
    return [
        key for key in _get_client().list_graphs() if key.startswith("customer:")
    ]
