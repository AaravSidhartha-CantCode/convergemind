"""FalkorDB connection and tenant-isolation boundary.

Every customer gets their own FalkorDB graph key. That is the isolation
mechanism: not a WHERE clause an agent could forget, but a separate
keyspace a query physically cannot traverse out of. Cross-customer
knowledge is deliberately placed in one shared graph instead, so the
only data that crosses a tenant boundary is data we explicitly put there.
"""

import os

from falkordb import FalkorDB

_client = None

SHARED_GRAPH_KEY = "shared:knowledge"


def _get_client() -> FalkorDB:
    global _client
    if _client is None:
        password = os.environ.get("FALKORDB_PASSWORD") or None
        _client = FalkorDB(
            host=os.environ.get("FALKORDB_HOST", "localhost"),
            port=int(os.environ.get("FALKORDB_PORT", "6379")),
            password=password,
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
