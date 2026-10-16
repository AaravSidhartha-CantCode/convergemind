"""CSS injection for the Signal Room direction.

Tokens are emitted as CSS custom properties so the bulk stylesheet below
stays a plain string with no interpolation, which keeps brace-escaping out
of the way and means a token change never touches a selector.
"""

from ui import theme

_FONT_IMPORTS = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Martian+Mono:wght@500;700&display=swap');"
    "@import url('https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap');"
)


def _vars() -> str:
    return (
        ":root{"
        f"--ink-base:{theme.INK_BASE};"
        f"--ink-raised:{theme.INK_RAISED};"
        f"--ink-canvas:{theme.INK_CANVAS};"
        f"--text-primary:{theme.TEXT_PRIMARY};"
        f"--text-muted:{theme.TEXT_MUTED};"
        f"--signal-amber:{theme.SIGNAL_AMBER};"
        f"--rule:{theme.RULE};"
        f"--mono:{theme.MONO_STACK};"
        f"--sans:{theme.SANS_STACK};"
        "}"
    )


_SHEET = """
/* ---- shell ---------------------------------------------------------- */
.stApp { background: var(--ink-base); }
.block-container { padding: 24px 0 24px 24px !important; max-width: 100% !important; }
#MainMenu, footer, header[data-testid="stHeader"] { display: none; }

/* ---- header --------------------------------------------------------- */
.cm-head {
  display: flex; align-items: baseline; justify-content: space-between;
  border-bottom: 1px solid var(--rule); padding-bottom: 12px; margin-bottom: 24px;
  padding-right: 24px;
}
.cm-title { font-family: var(--sans); font-weight: 700; font-size: 20px;
  color: var(--text-primary); letter-spacing: -0.01em; }
.cm-title span { color: var(--text-muted); font-weight: 400; margin-left: 12px;
  font-size: 13px; font-family: var(--mono); }
.cm-stats { display: flex; gap: 32px; }
.cm-stat { font-family: var(--mono); font-size: 11px; color: var(--text-muted);
  font-weight: 500; text-align: right; }
.cm-stat b { display: block; font-size: 18px; color: var(--text-primary);
  font-weight: 500; font-variant-numeric: tabular-nums; }

/* ---- panel labels --------------------------------------------------- */
.cm-label { font-family: var(--mono); font-weight: 700; font-size: 12px;
  color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.08em;
  display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.cm-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--signal-amber);
  transition: opacity 120ms ease-out; }
.cm-dot.idle { background: var(--rule); }

/* ---- conversation rails --------------------------------------------- */
.cm-rail { background: var(--ink-raised); border: 1px solid var(--rule);
  border-radius: 2px; padding: 16px; min-height: 420px; }
.cm-msg { margin-bottom: 12px; padding-bottom: 12px;
  border-bottom: 1px solid var(--rule); }
.cm-msg:last-child { border-bottom: none; }
.cm-msg-meta { font-family: var(--mono); font-size: 10px; color: var(--text-muted);
  font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em;
  margin-bottom: 4px; }
.cm-msg-body { font-family: var(--sans); font-size: 14px; line-height: 1.5;
  color: var(--text-primary); white-space: pre-wrap; }
.cm-empty { font-family: var(--mono); font-size: 11px; color: var(--text-muted); }

/* ---- tool trace ----------------------------------------------------- */
.cm-trace { font-family: var(--mono); font-size: 10px; color: var(--text-muted);
  margin-top: 8px; line-height: 1.7; }
.cm-trace b { color: var(--signal-amber); font-weight: 500; }

/* ---- tick-ruler spine: the one memorable element -------------------- */
/* Drawn in the gap between the two agents that never speak to each other. */
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) {
  position: relative;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2)::before {
  content: ""; position: absolute; left: -12px; top: 0; bottom: 0; width: 1px;
  background: repeating-linear-gradient(to bottom,
    var(--rule) 0 6px, transparent 6px 12px);
}

/* ---- graph canvas: no border, no padding, bleeds to the edge -------- */
.cm-canvas-label { font-family: var(--mono); font-weight: 700; font-size: 12px;
  color: var(--text-primary); text-transform: uppercase; letter-spacing: 0.08em;
  margin-bottom: 12px; }
.cm-legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 12px; }
.cm-legend span { font-family: var(--mono); font-size: 10px; color: var(--text-muted);
  display: flex; align-items: center; gap: 4px; }
.cm-swatch { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.cm-swatch.shared { border: 1px solid var(--text-primary); }

/* ---- shared knowledge ----------------------------------------------- */
.cm-know { border-top: 1px solid var(--rule); margin-top: 16px; padding-top: 16px; }
.cm-know-row { font-family: var(--mono); font-size: 11px; color: var(--text-primary);
  padding: 8px 0; border-bottom: 1px solid var(--rule); display: flex;
  justify-content: space-between; gap: 16px; }
.cm-know-row small { color: var(--text-muted); }
.cm-count { color: var(--signal-amber); font-variant-numeric: tabular-nums; }

/* ---- widgets -------------------------------------------------------- */
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
  background: var(--ink-base) !important; border: 1px solid var(--rule) !important;
  border-radius: 2px !important; color: var(--text-primary) !important;
  font-family: var(--mono) !important; font-size: 12px !important;
}
.stButton button, .stFormSubmitButton button {
  background: var(--ink-base); border: 1px solid var(--rule); border-radius: 2px;
  color: var(--text-primary); font-family: var(--mono); font-size: 11px;
  font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em;
}
.stButton button:hover, .stFormSubmitButton button:hover {
  border-color: var(--signal-amber); color: var(--signal-amber);
}
label, .stSelectbox label, .stTextInput label {
  font-family: var(--mono) !important; font-size: 10px !important;
  color: var(--text-muted) !important; text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* ---- tablet: agents side by side, graph full width beneath ---------- */
@media (max-width: 1100px) {
  div[data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  div[data-testid="stColumn"]:nth-of-type(3) { min-width: 100% !important; }
  div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2)::before {
    display: none;
  }
}
/* ---- mobile: single column, spine dropped rather than shrunk -------- */
@media (max-width: 640px) {
  .block-container { padding: 16px !important; }
  div[data-testid="stColumn"] { min-width: 100% !important; }
  .cm-head { flex-direction: column; gap: 12px; }
  .cm-stats { gap: 24px; }
}
"""


def inject() -> str:
    return f"<style>{_FONT_IMPORTS}{_vars()}{_SHEET}</style>"
