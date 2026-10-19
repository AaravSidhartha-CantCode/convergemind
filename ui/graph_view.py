"""Readable, customer-centered render of one customer's memory graph."""

import json

from ui import theme

_TEMPLATE = """
<!DOCTYPE html>
<html><head>
<script src="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js"
        integrity="sha384-6ox9IspbVlrc5vabD45kZcCJ8HeSwMAQjf9Iq48U/+srTVTNzsB7EqDC5oYpA0WC"
        crossorigin="anonymous"></script>
<style>
  html, body { margin: 0; padding: 0; background: __CANVAS__; }
  #net { width: 100%; height: __HEIGHT__px; background: __CANVAS__; }
</style>
</head><body>
<div id="net"></div>
<script>
  const nodes = new vis.DataSet(__NODES__);
  const edges = new vis.DataSet(__EDGES__);
  new vis.Network(document.getElementById("net"), {nodes, edges}, {
    layout: {
      hierarchical: {
        enabled: true, direction: "LR", sortMethod: "directed",
        levelSeparation: 145, nodeSpacing: 105, treeSpacing: 150,
        blockShifting: true, edgeMinimization: true, parentCentralization: true
      }
    },
    physics: false,
    interaction: { hover: true, zoomView: true, dragView: true, tooltipDelay: 120, navigationButtons: true },
    nodes: {
      shape: "box", margin: {top: 7, right: 9, bottom: 7, left: 9},
      borderWidth: 1, borderRadius: 4,
      font: { color: "__MUTED__", size: 10, face: "Martian Mono, monospace",
              strokeWidth: 0, vadjust: 0 }
    },
    edges: {
      color: { color: "__EDGE__", highlight: "__AMBER__" },
      width: 1, smooth: false,
      font: { color: "__MUTED__", size: 8, face: "Martian Mono, monospace",
              strokeWidth: 0, align: "horizontal" },
      arrows: { to: { enabled: true, scaleFactor: 0.4 } }
    }
  });
</script>
</body></html>
"""


def render_html(snapshot: dict, height: int = 520) -> str:
    nodes = []
    levels = {
        "Customer": 0,
        "Session": 1,
        "Agent": 2,
        "Fact": 2,
        "Issue": 2,
        "MemoryClaim": 2,
        "Evidence": 3,
        "Decision": 3,
        "HandoffCapsule": 3,
    }
    for node in snapshot["nodes"]:
        label = node["label"]
        is_shared = label in theme.SHARED_LABELS
        nodes.append(
            {
                "id": node["id"],
                "label": _wrap_caption(node["caption"]),
                "title": f"{label}\n" + "\n".join(
                    f"{k}: {v}" for k, v in node["properties"].items()
                ),
                "color": {
                    "background": theme.NODE_FILL.get(label, theme.TEXT_MUTED),
                    "border": theme.TEXT_PRIMARY,
                },
                "borderWidth": 1 if is_shared else 0,
                "size": 20 if label == "Customer" else 13,
                "shape": "ellipse" if label == "Customer" else "box",
                "level": levels.get(label, 3),
            }
        )
    edges = [
        {
            "from": edge["source"],
            "to": edge["target"],
            "label": edge["type"]
            if edge["type"] in {"NEXT", "SUPERSEDES", "CONTRADICTS", "DEPENDS_ON"}
            else "",
        }
        for edge in snapshot["edges"]
    ]

    return (
        _TEMPLATE.replace("__NODES__", json.dumps(nodes))
        .replace("__EDGES__", json.dumps(edges))
        .replace("__CANVAS__", theme.INK_CANVAS)
        .replace("__MUTED__", theme.TEXT_MUTED)
        .replace("__EDGE__", theme.EDGE)
        .replace("__AMBER__", theme.SIGNAL_AMBER)
        .replace("__HEIGHT__", str(height))
    )


def _wrap_caption(caption: str, width: int = 22) -> str:
    """Keep graph labels readable instead of letting one fact dominate a row."""
    words = caption.split()
    lines, line = [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and len(candidate) > width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return "\n".join(lines[:3])


def legend_html() -> str:
    """Legend for the customer canvas only.

    Shared-graph labels are intentionally omitted: this canvas renders one
    tenant's keyspace, so IssueType and Resolution genuinely cannot appear
    in it. Cross-tenant reuse is shown in the shared knowledge panel
    beneath instead, with the customer each fix was learned from.
    """
    items = []
    for label, fill in theme.NODE_FILL.items():
        if label in theme.SHARED_LABELS:
            continue
        items.append(
            f'<span><i class="cm-swatch" style="background:{fill}"></i>{label}</span>'
        )
    items.append(
        '<span style="opacity:.7">this canvas is one tenant keyspace</span>'
    )
    return f'<div class="cm-legend">{"".join(items)}</div>'
