"""Signal Room tokens. The only place a hex literal is allowed to appear.

Locked in 01 Planning/Design.md. Contrast ratios verified there, not guessed:
text-primary on ink-base is 14.28:1, every graph node fill clears 6.9:1
against ink-canvas, and the edge colour clears the 3:1 graphic-mark floor.
"""

INK_BASE = "#10141A"
INK_RAISED = "#171C24"
INK_CANVAS = "#0B0E13"
TEXT_PRIMARY = "#DCE3EC"
TEXT_MUTED = "#8C98A8"
SIGNAL_AMBER = "#E8A33D"
RULE = "#222A35"

# Graph node fills by label.
NODE_FILL = {
    "Customer": "#F2C14E",
    "Session": "#6FA8FF",
    "Fact": "#5FD0BE",
    "Issue": "#F2756B",
    "IssueType": "#C39BF0",
    "Resolution": "#9ED47A",
    # Agents are actors, not memory. Deliberately desaturated and square
    # (see graph_view) so they read as the things acting on the graph
    # rather than as another kind of remembered thing.
    "Agent": "#7D8B9E",
}
EDGE = "#54657F"

ACTOR_LABELS = {"Agent"}

# Nodes that live in the shared cross-tenant graph get a stroke; the
# customer's own nodes do not. That is the isolation tell, and it survives
# a greyscale screenshot.
SHARED_LABELS = {"IssueType", "Resolution"}

# Spacing scale, px. No eyeballed values.
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "2xl": 32, "3xl": 48}

MONO_STACK = "'Martian Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
SANS_STACK = "'Satoshi', system-ui, -apple-system, sans-serif"
