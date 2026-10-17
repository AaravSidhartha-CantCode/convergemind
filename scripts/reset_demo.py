"""Drop every demo graph and reseed. Run before recording.

The test suite writes throwaway tenants and issue types into the shared
knowledge graph. They are harmless, but 'issue types: 9' on screen when
four are real looks careless, and the header counters are visible in the
first frame of the video.

Usage:  python -m scripts.reset_demo
"""

from backend.db import SHARED_GRAPH_KEY, _get_client, get_shared_graph
from backend.seed_data import seed_all


def drop_all() -> int:
    client = _get_client()
    dropped = 0
    for key in client.list_graphs():
        if key.startswith("customer:") or key == SHARED_GRAPH_KEY:
            try:
                client.select_graph(key).delete()
                dropped += 1
            except Exception as exc:
                print(f"   could not drop {key}: {exc}")
    return dropped


if __name__ == "__main__":
    dropped = drop_all()
    print(f"Dropped {dropped} graph keys.")
    seeded = seed_all()
    print(f"Reseeded {len(seeded)} customers: {', '.join(seeded)}")
    issue_types = get_shared_graph().query(
        "MATCH (t:IssueType) RETURN count(t)"
    ).result_set[0][0]
    print(f"Shared knowledge graph holds {issue_types} issue types.")
    print("Demo state is clean.")
