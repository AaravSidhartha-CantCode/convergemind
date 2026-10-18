"""Index setup, applied idempotently.

FalkorDB raises on a duplicate index rather than offering IF NOT EXISTS,
so a duplicate is swallowed and anything else is re-raised. Swallowing
every exception here would hide a genuinely malformed index statement.
"""

CUSTOMER_INDEXES = [
    "CREATE INDEX FOR (c:Customer) ON (c.id)",
    "CREATE INDEX FOR (s:Session) ON (s.id)",
    "CREATE INDEX FOR (f:Fact) ON (f.key)",
    "CREATE INDEX FOR (i:Issue) ON (i.id)",
    "CREATE INDEX FOR (m:MemoryClaim) ON (m.id)",
    "CREATE INDEX FOR (d:Decision) ON (d.id)",
    "CREATE INDEX FOR (h:HandoffCapsule) ON (h.id)",
]

SHARED_INDEXES = [
    "CREATE INDEX FOR (t:IssueType) ON (t.name)",
    "CREATE INDEX FOR (r:Resolution) ON (r.id)",
]


def _apply(graph, statements) -> None:
    for stmt in statements:
        try:
            graph.query(stmt)
        except Exception as exc:
            if "already" not in str(exc).lower():
                raise


def apply_customer_schema(graph) -> None:
    _apply(graph, CUSTOMER_INDEXES)


def apply_shared_schema(graph) -> None:
    _apply(graph, SHARED_INDEXES)
