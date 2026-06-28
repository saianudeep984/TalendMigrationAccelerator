import uuid
"""
TMA Design System v2 — PHASE 1 UI REFACTOR
Converts shell to enterprise dashboard:
  - Top navigation bar (replaces sidebar nav)
  - Compact padding / whitespace
  - 4-column KPI layout utility
  - Fixed-height panel component
  - Compact page header component
All original component functions are preserved unchanged.
"""

try:
    import streamlit as st
except ImportError:
    import types as _types

    class _StCol:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def __getattr__(self, name): return lambda *a, **kw: None

    class _Stub:
        def __call__(self, *a, **kw): return _StCol()
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def __getattr__(self, name): return lambda *a, **kw: None

    _stub_inst = _Stub()

    def _cache_data(*a, **kw):
        if a and callable(a[0]):
            return a[0]
        return lambda fn: fn

    st = _types.SimpleNamespace(
        cache_data=_cache_data,
        markdown=lambda *a, **kw: None,
        write=lambda *a, **kw: None,
        caption=lambda *a, **kw: None,
        columns=lambda n, **kw: [_StCol() for _ in range(n if isinstance(n, int) else len(n))],
        tabs=lambda names: [_StCol() for _ in names],
        metric=lambda *a, **kw: None,
        subheader=lambda *a, **kw: None,
        header=lambda *a, **kw: None,
        info=lambda *a, **kw: None,
        warning=lambda *a, **kw: None,
        error=lambda *a, **kw: None,
        success=lambda *a, **kw: None,
        plotly_chart=lambda *a, **kw: None,
        divider=lambda *a, **kw: None,
        empty=lambda *a, **kw: _StCol(),
        expander=lambda *a, **kw: _StCol(),
        container=lambda *a, **kw: _StCol(),
        sidebar=_stub_inst,
        spinner=lambda *a, **kw: _StCol(),
        button=lambda *a, **kw: False,
        selectbox=lambda *a, **kw: None,
        multiselect=lambda *a, **kw: [],
        text_input=lambda *a, **kw: "",
        number_input=lambda *a, **kw: 0,
        checkbox=lambda *a, **kw: False,
        radio=lambda *a, **kw: None,
        download_button=lambda *a, **kw: False,
        session_state={},
        set_page_config=lambda *a, **kw: None,
        rerun=lambda: None,
        stop=lambda: None,
        image=lambda *a, **kw: None,
        progress=lambda *a, **kw: None,
        dataframe=lambda *a, **kw: None,
        table=lambda *a, **kw: None,
        toast=lambda *a, **kw: None,
        status=lambda *a, **kw: _StCol(),
        title=lambda *a, **kw: None,
        popover=lambda *a, **kw: _StCol(),
        link_button=lambda *a, **kw: False,
        pills=lambda *a, **kw: None,
        segmented_control=lambda *a, **kw: None,
        feedback=lambda *a, **kw: None,
        dialog=lambda *a, **kw: (lambda fn: fn),
        html=lambda *a, **kw: None,
    )
import base64
import html
import imghdr
import os
import re


# ── Mermaid → Graphviz (offline diagram rendering) ──────────────────────────────
# Streamlit renders st.graphviz_chart() entirely client-side using its own
# bundled viz.js — no external CDN required. This parses the small subset of
# Mermaid flowchart syntax used across this app (graph LR/TD, node shapes
# [...]/(...)/{...}/([...])/[(...)], edges with optional |label|, and
# class/classDef styling) and converts it into an equivalent DOT graph.

_MERMAID_NODE_RE = re.compile(
    r'^(?P<id>[A-Za-z0-9_]+)'
    r'(?:'
    r'\[\((?P<cyl>.*)\)\]'      # [("label")]  -> cylinder
    r'|\(\[(?P<stadium>.*)\]\)' # (["label"])  -> stadium / rounded
    r'|\{(?P<diamond>.*)\}'     # {"label"}    -> diamond
    r'|\[(?P<box>.*)\]'         # ["label"]    -> box
    r')?$'
)

_MERMAID_EDGE_RE = re.compile(
    r'^(?P<left>.+?)\s*-->\s*(?:\|(?P<label>.*?)\|\s*)?(?P<right>.+)$'
)

_MERMAID_CLASS_RE = re.compile(r'^class\s+([A-Za-z0-9_,\s]+)\s+([A-Za-z0-9_]+)\s*;?$')
_MERMAID_CLASSDEF_RE = re.compile(r'^classDef\s+([A-Za-z0-9_]+)\s+(.*?);?$')


def _dot_label(text: str) -> str:
    if text is None:
        text = ""
    text = text.strip().strip('"')
    text = text.replace("<br/>", "\n").replace("<br>", "\n").replace("\\n", "\n")
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\n", "\\n")
    return text


def mermaid_to_dot(mermaid_code: str) -> str:
    """Convert a small subset of Mermaid flowchart syntax into a DOT graph string."""
    direction = "LR"
    nodes = {}      # id -> (label, shape, style)
    node_order = []
    edges = []      # (src, dst, label)
    class_defs = {}  # style name -> {fillcolor, color, fontcolor}
    node_classes = {}  # id -> style name

    def _register_node(node_id: str, shape_part: str | None):
        if node_id not in nodes:
            nodes[node_id] = [node_id, "box", None]
            node_order.append(node_id)
        if shape_part:
            m = _MERMAID_NODE_RE.match(node_id + shape_part)
            if m:
                if m.group("cyl") is not None:
                    nodes[node_id][0] = _dot_label(m.group("cyl"))
                    nodes[node_id][1] = "cylinder"
                elif m.group("stadium") is not None:
                    nodes[node_id][0] = _dot_label(m.group("stadium"))
                    nodes[node_id][1] = "ellipse"
                elif m.group("diamond") is not None:
                    nodes[node_id][0] = _dot_label(m.group("diamond"))
                    nodes[node_id][1] = "diamond"
                elif m.group("box") is not None:
                    nodes[node_id][0] = _dot_label(m.group("box"))
                    nodes[node_id][1] = "box"

    def _split_endpoint(text: str):
        text = text.strip()
        m = re.match(r'^([A-Za-z0-9_]+)(.*)$', text)
        if not m:
            return text, None
        return m.group(1), (m.group(2) or None)

    for raw_line in mermaid_code.splitlines():
        line = raw_line.strip().rstrip(";")
        if not line:
            continue
        if line.startswith(("graph ", "flowchart ")):
            parts = line.split()
            if len(parts) > 1 and parts[1] in ("LR", "RL", "TD", "TB", "BT"):
                direction = "LR" if parts[1] in ("LR", "RL") else "TB"
            continue

        m_classdef = _MERMAID_CLASSDEF_RE.match(line)
        if m_classdef:
            style_name, body = m_classdef.groups()
            style = {}
            for kv in body.split(","):
                if ":" not in kv:
                    continue
                k, v = kv.split(":", 1)
                k, v = k.strip(), v.strip()
                if k == "fill":
                    style["fillcolor"] = v
                elif k == "stroke":
                    style["color"] = v
                elif k == "color":
                    style["fontcolor"] = v
            class_defs[style_name] = style
            continue

        m_class = _MERMAID_CLASS_RE.match(line)
        if m_class:
            ids_part, style_name = m_class.groups()
            for nid in ids_part.split(","):
                nid = nid.strip()
                if nid:
                    node_classes[nid] = style_name
            continue

        m_edge = _MERMAID_EDGE_RE.match(line)
        if m_edge:
            left, label, right = m_edge.group("left"), m_edge.group("label"), m_edge.group("right")
            src_id, src_shape = _split_endpoint(left)
            dst_id, dst_shape = _split_endpoint(right)
            _register_node(src_id, src_shape)
            _register_node(dst_id, dst_shape)
            edges.append((src_id, dst_id, _dot_label(label) if label else None))
            continue

        node_id, shape_part = _split_endpoint(line)
        if shape_part:
            _register_node(node_id, shape_part)

    # Use minlen=2 only when there are enough nodes to benefit from extra rank distance
    _minlen = 2 if len(node_order) > 4 else 1
    lines = [
        "digraph G {",
        f'  rankdir={direction};',
        '  bgcolor="transparent";',
        '  nodesep=0.7;',
        '  ranksep=1.0;',
        '  pad=0.4;',
        '  splines=curved;',
        '  concentrate=true;',
        '  node [fontname="Helvetica", fontsize=11, style="rounded,filled", '
        'fillcolor="#27314a", fontcolor="#e2e8f0", color="#475569", '
        'margin="0.2,0.14", width=1.6];',
        '  edge [fontname="Helvetica Bold", fontsize=11, color="#2563eb", fontcolor="#1e40af", '
        f'penwidth=2.0, arrowsize=1.2, arrowhead=vee, minlen={_minlen}];',
    ]
    for nid in node_order:
        label, shape, _ = nodes[nid]
        attrs = [f'label="{label}"']
        if shape == "diamond":
            attrs.append('shape=diamond')
            attrs.append('width=2.0')
        elif shape == "cylinder":
            attrs.append('shape=cylinder')
            attrs.append('labelloc=c')
        elif shape == "ellipse":
            attrs.append('shape=ellipse')
            attrs.append('labelloc=c')
        else:
            attrs.append('shape=box')
        style_name = node_classes.get(nid)
        if style_name and style_name in class_defs:
            cd = class_defs[style_name]
            # classDef nodes get light backgrounds — reset fontcolor to dark for readability
            if "fillcolor" in cd:
                attrs.append(f'fillcolor="{cd["fillcolor"]}"')
                attrs.append('fontcolor="#1a1a18"')
            if "color" in cd:
                attrs.append(f'color="{cd["color"]}"')
                attrs.append('penwidth=2.0')
        lines.append(f'  "{nid}" [{", ".join(attrs)}];')
    for src, dst, label in edges:
        if label:
            attr = f' [label="{label}", color="#2563eb", fontcolor="#1e40af", penwidth=2.0]'
        else:
            attr = ' [color="#2563eb", penwidth=2.0]'
        lines.append(f'  "{src}" -> "{dst}"{attr};')
    if not node_order:
        lines.append('  EMPTY [label="No data available", shape=box];')
    lines.append("}")
    return "\n".join(lines)


def render_mermaid_diagram(mermaid_code: str, height: int = 420) -> None:
    """Render a Mermaid-style flowchart fully offline via st.graphviz_chart()."""
    dot_source = mermaid_to_dot(mermaid_code)
    st.graphviz_chart(dot_source, use_container_width=True)


# ── Logo ───────────────────────────────────────────────────────────────────────
_LOGO_FILENAME = "artha_logo.png"


@st.cache_data(show_spinner=False)
def _load_logo_data_uri() -> str | None:
    """Resolve and base64-encode the Artha logo for inline use in the top nav."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, _LOGO_FILENAME),
        os.path.join(here, "assets", _LOGO_FILENAME),
        os.path.join(here, "..", _LOGO_FILENAME),
        os.path.join(here, "..", "assets", _LOGO_FILENAME),
        os.path.join(here, "..", "..", "assets", _LOGO_FILENAME),
        os.path.join(os.getcwd(), _LOGO_FILENAME),
        os.path.join(os.getcwd(), "assets", _LOGO_FILENAME),
    ]
    raw = None
    for logo_path in candidates:
        try:
            with open(logo_path, "rb") as f:
                raw = f.read()
            break
        except OSError:
            continue
    if raw is None:
        return None
    kind = imghdr.what(None, h=raw) or "png"
    mime = "image/jpeg" if kind in ("jpeg", "jpg") else f"image/{kind}"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


# ── Theme ──────────────────────────────────────────────────────────────────────

def apply_wizard_theme() -> None:
    """
    PHASE 1 UI REFACTOR
    Enterprise dashboard theme.
    - Hides the Streamlit sidebar entirely (nav moved to top bar)
    - Reduces block-container padding for denser layout
    - Adds .tma-topnav, .tma-panel, .tma-page-header, .tma-kpi-grid CSS
    - Preserves all existing component classes
    """
    if "tma_theme" not in st.session_state:
        st.session_state["tma_theme"] = "Light"

    _t = st.session_state.get("tma_theme")
    if not st.session_state.get("_theme_injected") or st.session_state.get("_theme_last") != _t:
        st.session_state["_theme_injected"] = True
        st.session_state["_theme_last"] = _t

    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Design tokens ── */
:root {
    --tma-primary: #2563eb;
    --tma-primary-dark: #1d4ed8;
    --tma-primary-light: #eff6ff;
    --tma-accent: #7c3aed;
    --tma-text: #0f172a;
    --tma-text-muted: #64748b;
    --tma-border: #e2e8f0;
    --tma-bg: #f4f6fb;
    --tma-surface: #ffffff;
    --tma-radius: 10px;
    --tma-shadow-sm: 0 1px 2px rgba(15, 23, 42, .05);
    --tma-shadow-md: 0 4px 14px rgba(15, 23, 42, .07);
    --tma-shadow-lg: 0 10px 30px rgba(15, 23, 42, .10);
}

/* ── Base ── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, sans-serif !important;
    background: var(--tma-bg) !important;
    background-image: radial-gradient(circle at 0% 0%, #eef2ff 0%, transparent 32%),
                       radial-gradient(circle at 100% 0%, #ecfeff 0%, transparent 32%) !important;
    background-attachment: fixed !important;
    color: var(--tma-text) !important;
}

/* ── Performance: avoid dim/fade flash on rerun (tab navigation) ── */
/* Suppress the default Streamlit stale-fade on everything EXCEPT tab panels
   (tab panels fade out fast so the skeleton can appear cleanly) */
[data-stale="true"] { opacity: 1 !important; transition: none !important; filter: none !important; }
[data-stale="true"] .stTabs [data-baseweb="tab-panel"] {
    opacity: 0.08 !important;
    transition: opacity 0.1s ease !important;
}

/* PHASE 1 UI REFACTOR — reduced block padding for denser dashboard layout */
/* PHASE 7 UI REFACTOR */
.block-container {
    padding: 52px 1rem 1rem !important;
    max-width: 1400px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* PHASE 7 UI REFACTOR — compact enterprise typography and spacing */
h1, h2, h3, h4, h5, h6 { letter-spacing: -.01em !important; color: var(--tma-text) !important; }
h1 { font-size: 1.35rem !important; font-weight: 800 !important; }
h2 { font-size: 1.12rem !important; font-weight: 700 !important; }
h3 { font-size: 1rem !important; font-weight: 700 !important; }
p, li, label, .stMarkdown, .stCaption { font-size: 0.9rem; }
div[data-testid="stVerticalBlock"] { gap: .35rem !important; }
hr { margin: .6rem 0 .8rem !important; border-color: var(--tma-border) !important; }

/* PHASE 1 UI REFACTOR — hide sidebar completely; navigation is now in the top bar */
section[data-testid="stSidebar"] {
    display: none !important;
}
/* Widen main area when sidebar is hidden */
.css-1d391kg, [data-testid="stSidebarNav"] { display: none !important; }

/* ── Native Streamlit overrides ── */
div[data-testid="stMetric"] {
    background: var(--tma-surface) !important;
    border: 1px solid var(--tma-border) !important;
    border-radius: var(--tma-radius) !important;
    padding: 10px 12px !important;
    min-height: 70px !important;
    box-shadow: var(--tma-shadow-sm) !important;
    transition: box-shadow .15s ease, transform .15s ease !important;
}
div[data-testid="stMetric"]:hover {
    box-shadow: var(--tma-shadow-md) !important;
    transform: translateY(-1px) !important;
}
div[data-testid="stMetricValue"] {
    font-size: 21px !important; font-weight: 800 !important; line-height: 1.05 !important;
    background: linear-gradient(135deg, var(--tma-primary-dark), var(--tma-accent));
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
div[data-testid="stMetricLabel"] {
    font-size: 10px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: .06em !important;
    color: var(--tma-text-muted) !important;
}

.stTabs [data-baseweb="tab-list"] {
    border-bottom: none !important;
    background: #eef2f7 !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 12px !important;
    font-weight: 600 !important;
    color: var(--tma-text-muted) !important;
    padding: 7px 16px !important;
    border-radius: 8px !important;
    border-bottom: none !important;
    background: transparent !important;
    margin-bottom: 0 !important;
    letter-spacing: 0 !important;
    transition: background .15s ease, color .15s ease !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--tma-primary-dark) !important; }
.stTabs [aria-selected="true"] {
    color: var(--tma-primary-dark) !important;
    background: var(--tma-surface) !important;
    box-shadow: var(--tma-shadow-sm) !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 12px !important; }

/* ── Tab transition: instant clear + skeleton shimmer ── */
/* When Streamlit marks content as stale (mid-rerun), fade it out fast
   so old tab content doesn't linger visibly */
[data-stale="true"] .stTabs [data-baseweb="tab-panel"],
[data-stale="true"] .stTabs [data-baseweb="tab-panel"] * {
    opacity: 0 !important;
    transition: opacity 0.08s ease !important;
}

/* Skeleton shimmer keyframe */
@keyframes tma-shimmer {
    0%   { background-position: -600px 0; }
    100% { background-position: 600px 0; }
}

/* Skeleton bar base — use class .tma-skel on any div */
.tma-skel {
    background: linear-gradient(90deg, #e8eaf0 25%, #f4f6fb 50%, #e8eaf0 75%);
    background-size: 600px 100%;
    animation: tma-shimmer 1.3s ease-in-out infinite;
    border-radius: 6px;
    display: block;
}

/* Pre-built skeleton card for tab loading state */
.tma-tab-loading {
    padding: 18px 0 8px;
}
.tma-tab-loading .tma-skel-title {
    height: 18px; width: 38%; margin-bottom: 18px;
}
.tma-tab-loading .tma-skel-kpi-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 18px;
}
.tma-tab-loading .tma-skel-kpi {
    height: 72px; border-radius: 10px;
}
.tma-tab-loading .tma-skel-line { height: 12px; margin-bottom: 10px; border-radius: 4px; }
.tma-tab-loading .tma-skel-line.w100 { width: 100%; }
.tma-tab-loading .tma-skel-line.w80  { width: 80%; }
.tma-tab-loading .tma-skel-line.w60  { width: 60%; }
.tma-tab-loading .tma-skel-block { height: 120px; width: 100%; margin-bottom: 14px; border-radius: 10px; }
.stButton > button {
    font-size: 12px !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    padding: 5px 12px !important;
    min-height: 30px !important;
    border: 1px solid var(--tma-border) !important;
    background: var(--tma-surface) !important;
    color: #334155 !important;
    box-shadow: var(--tma-shadow-sm) !important;
    transition: all .15s ease !important;
}
.stButton > button:hover {
    background: var(--tma-primary-light) !important;
    border-color: var(--tma-primary) !important;
    color: var(--tma-primary-dark) !important;
    box-shadow: var(--tma-shadow-md) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--tma-primary), var(--tma-accent)) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: var(--tma-shadow-md) !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: var(--tma-shadow-lg) !important;
    transform: translateY(-1px) !important;
    filter: brightness(1.05);
}
.stDownloadButton > button {
    background: linear-gradient(135deg, var(--tma-primary), var(--tma-accent)) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    box-shadow: var(--tma-shadow-md) !important;
    transition: all .15s ease !important;
}
.stDownloadButton > button:hover {
    box-shadow: var(--tma-shadow-lg) !important;
    transform: translateY(-1px) !important;
}
[data-testid="stFileUploader"] {
    border: 2px dashed #cbd5e1 !important;
    border-radius: var(--tma-radius) !important;
    padding: 10px !important;
    background: var(--tma-surface) !important;
    transition: border-color .15s ease !important;
}
[data-testid="stFileUploader"]:hover { border-color: var(--tma-primary) !important; }
.stSelectbox label, .stTextInput label, .stTextArea label, .stNumberInput label,
.stCheckbox label, .stSlider label {
    font-size: 12px !important;
    color: #334155 !important;
    font-weight: 600 !important;
}
.stSelectbox > div > div, .stTextInput > div > div, .stTextArea > div, .stNumberInput > div > div {
    border-radius: 8px !important;
    transition: border-color .15s ease, box-shadow .15s ease !important;
}
.stSelectbox > div > div:focus-within, .stTextInput > div > div:focus-within,
.stTextArea > div:focus-within, .stNumberInput > div > div:focus-within {
    border-color: var(--tma-primary) !important;
    box-shadow: 0 0 0 3px var(--tma-primary-light) !important;
}
.stProgress > div { background: transparent !important; }
.stProgress > div > div { background: var(--tma-border) !important; border-radius: 99px !important; }
.stProgress > div > div > div { background: #15803d !important; border-radius: 99px !important; }
.stAlert { border-radius: 10px !important; font-size: 13px !important; box-shadow: var(--tma-shadow-sm) !important; }


div[data-testid="stHorizontalBlock"] {
    gap: .6rem !important;
    align-items: stretch !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
    min-width: 0 !important;
}
div[data-testid="stHorizontalBlock"] > div[data-testid="column"] > div {
    min-width: 0 !important;
}
.stButton,
.stDownloadButton,
.stButton > button,
.stDownloadButton > button {
    max-width: 100% !important;
    box-sizing: border-box !important;
}
.stButton > button,
.stDownloadButton > button {
    min-width: 0 !important;
    white-space: normal !important;
}
.stButton > button p,
.stDownloadButton > button p {
    overflow-wrap: anywhere !important;
    word-break: break-word !important;
}
@media (max-width: 900px) {
    .block-container {
        padding-left: .75rem !important;
        padding-right: .75rem !important;
    }
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: .5rem !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        flex: 1 1 220px !important;
        min-width: min(100%, 220px) !important;
    }
}
@media (max-width: 640px) {
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        flex-basis: 100% !important;
        width: 100% !important;
    }
}
.tma-nav-row {
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    margin: 0 0 .45rem;
    padding: .25rem .75rem;
    position: relative;
    z-index: 1;
    box-shadow: 0 1px 3px rgba(15, 23, 42, .06);
}
.tma-nav-brand {
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
    line-height: 1.1;
    padding-top: 3px;
}
.tma-nav-sub {
    font-size: 10px;
    color: #64748b;
    font-weight: 500;
}
.tma-nav-status {
    text-align: right;
    font-size: 11px;
    color: #64748b;
    padding-top: 5px;
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   PHASE 1 UI REFACTOR — TOP NAVIGATION BAR
   Replaces the Streamlit sidebar radio nav with a fixed horizontal bar.
   .tma-topnav          outer wrapper (full-width, white, border-bottom)
   .tma-topnav-brand    logo + product name on the left
   .tma-topnav-links    nav link row in the centre
   .tma-topnav-link     individual pill link
   .tma-topnav-link.active  highlighted active link
   .tma-topnav-status   repository status chip on the right
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.tma-topnav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 0 1.25rem;
    height: 50px;
    margin: 0 0 .75rem;
    position: relative;
    z-index: 1;
    box-shadow: 0 1px 3px rgba(0,0,0,.06);
}
.tma-topnav-brand {
    display: flex;
    align-items: center;
    gap: 9px;
    flex-shrink: 0;
}
.tma-topnav-logo {
    width: 28px;
    height: 28px;
    background: #1d4ed8;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    color: #fff;
    flex-shrink: 0;
}
.tma-topnav-name  { font-size: 13px; font-weight: 800; color: #0f172a; line-height: 1.2; }
.tma-topnav-sub   { font-size: 10px; color: #64748b; }
.tma-topnav-links {
    display: flex;
    align-items: center;
    gap: 2px;
}
.tma-topnav-link {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 5px 11px;
    border-radius: 7px;
    font-size: 12px;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
    border: 1px solid transparent;
    transition: all .15s;
    white-space: nowrap;
    text-decoration: none;
}
.tma-topnav-link:hover {
    background: #f1f5f9;
    color: #1d4ed8;
}
.tma-topnav-link.active {
    background: #eff6ff;
    color: #1d4ed8;
    font-weight: 600;
    border-color: #bfdbfe;
}
.tma-nav-group-sep {
    display: inline-block;
    width: 1px;
    height: 20px;
    background: #e2e8f0;
    margin: 0 2px;
    flex-shrink: 0;
}
.tma-topnav-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
}
.tma-topnav-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #64748b;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 99px;
    padding: 4px 10px;
    white-space: nowrap;
}
.tma-status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    flex-shrink: 0;
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   PHASE 1 UI REFACTOR — 4-COLUMN KPI GRID UTILITY
   Usage in Python: wrap four metric_card() calls inside
       kpi_grid_open() … kpi_grid_close()
   or use the render_kpi_grid() helper below.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.tma-kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
    margin-bottom: 8px;
}
.tma-kpi-grid-item {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 11px;
    min-height: 66px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
}
.tma-kpi-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: #64748b;
    margin-bottom: 4px;
}
.tma-kpi-value {
    font-size: 21px;
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 3px;
}
.tma-kpi-caption { font-size: 11px; color: #94a3b8; }
@media (max-width: 900px) {
    .tma-kpi-grid { grid-template-columns: repeat(2, 1fr); }
    .tma-topnav { height: auto; align-items: flex-start; flex-wrap: wrap; padding: .6rem 1rem; }
    .tma-topnav-links { order: 3; width: 100%; overflow-x: auto; padding-top: .35rem; }
    .tma-topnav-status { display: none; }
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   PHASE 1 UI REFACTOR — FIXED-HEIGHT PANEL COMPONENT
   .tma-panel            white card with fixed height and scroll
   .tma-panel-header     panel title bar
   .tma-panel-body       scrollable content area
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.tma-panel {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    margin-bottom: 8px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
}
.tma-panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 7px 10px;
    border-bottom: 1px solid #f1f5f9;
    background: #fafbfc;
    flex-shrink: 0;
}
.tma-panel-title {
    font-size: 13px;
    font-weight: 600;
    color: #0f172a;
}
.tma-panel-subtitle { font-size: 11px; color: #94a3b8; margin-top: 1px; }
.tma-panel-body {
    overflow-y: auto;
    padding: 8px 10px;
    flex: 1;
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   PHASE 1 UI REFACTOR — COMPACT PAGE HEADER
   .tma-page-header   full-width coloured header strip per page
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
.tma-page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    background: linear-gradient(120deg, #0b1d3a 0%, #1d4ed8 100%);
    color: #fff;
    border-radius: 14px;
    padding: 20px 24px;
    margin: 16px 0 16px 0;
    box-shadow: 0 2px 12px rgba(15, 23, 42, .12);
}
.tma-page-header-icon {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: rgba(255, 255, 255, .18);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    flex-shrink: 0;
}
.tma-page-header-title {
    font-size: 22px;
    font-weight: 800;
    color: #fff;
    letter-spacing: .01em;
    line-height: 1.2;
}
.tma-page-header-sub { font-size: 13px; color: rgba(255,255,255,.8); margin-top: 3px; }

/* ── Existing component classes (unchanged from previous design_system_v2) ── */
/* status_card, success_banner, download_card, metric_card, section_header,
   wizard_progress, page_title — all their inline styles are in the Python
   functions below and remain identical. */

/* Scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
@media (max-width: 560px) {
    /* PHASE 7 UI REFACTOR */
    .block-container { padding: 52px .6rem .9rem !important; }
    .tma-kpi-grid { grid-template-columns: 1fr; }
    .tma-page-header { align-items: flex-start; }
}
/* ── Legacy component classes (design_system.py: hero/section/metric_card/
   action_panel/roadmap) — these pages were never migrated off the old
   helper functions, and apply_enterprise_theme() (the only place that used
   to style them) is no longer called anywhere. Without this block, those
   cards render with zero matching CSS the moment a repository is uploaded
   and the user reaches Command Center / Migration Advisor, which is the
   "layout changes after upload" inconsistency. Re-mapped onto the same
   --tma-* tokens used everywhere else so the theme matches. ── */
.f-hero {
    background: linear-gradient(118deg, #0f172a 0%, #1e3a5f 60%, #0f4c75 100%);
    border-radius: 14px;
    padding: 22px 26px;
    color: #fff;
    margin-bottom: 20px;
}
.f-hero-title { font-size: 19px; font-weight: 700; margin: 0 0 3px; letter-spacing: -0.01em; }
.f-hero-sub   { font-size: 12px; color: rgba(255,255,255,0.7); margin: 0 0 12px; line-height: 1.5; }
.f-pill-row   { display: flex; flex-wrap: wrap; gap: 6px; }
.f-pill {
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.18);
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    color: rgba(255,255,255,0.88);
}
.f-section {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin: 20px 0 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--tma-border);
}
.f-section-title { font-size: 13px; font-weight: 600; color: var(--tma-text); }
.f-section-sub   { font-size: 12px; color: var(--tma-text-muted); }
.f-kpi {
    background: var(--tma-surface);
    border: 1px solid var(--tma-border);
    border-radius: var(--tma-radius);
    padding: 14px 16px;
    box-shadow: var(--tma-shadow-sm);
    min-height: 86px;
}
.f-kpi-label   { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--tma-text-muted); margin-bottom: 5px; }
.f-kpi-value   { font-size: 22px; font-weight: 700; color: var(--tma-text); line-height: 1.1; margin-bottom: 3px; }
.f-kpi-caption { font-size: 11px; color: var(--tma-text-muted); line-height: 1.4; }
.f-kpi-bar     { height: 2px; border-radius: 999px; margin-top: 9px; }
.f-action {
    background: var(--tma-surface);
    border: 1px solid var(--tma-border);
    border-left: 3px solid var(--tma-primary);
    border-radius: var(--tma-radius);
    padding: 12px 14px;
    box-shadow: var(--tma-shadow-sm);
    height: 100%;
}
.f-action-title  { font-size: 13px; font-weight: 600; color: var(--tma-text); margin-bottom: 4px; }
.f-action-body   { font-size: 12px; color: var(--tma-text-muted); line-height: 1.4; margin-bottom: 6px; }
.f-action-status { font-size: 11px; font-weight: 600; }
.f-roadmap { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 8px 0 16px; }
.f-step {
    background: var(--tma-surface);
    border: 1px solid var(--tma-border);
    border-radius: var(--tma-radius);
    padding: 12px 14px;
    box-shadow: var(--tma-shadow-sm);
}
.f-step-num   { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--tma-primary); margin-bottom: 4px; }
.f-step-title { font-size: 13px; font-weight: 600; color: var(--tma-text); margin-bottom: 3px; }
.f-step-desc  { font-size: 11px; color: var(--tma-text-muted); line-height: 1.4; }
@media (max-width: 900px) {
    .f-roadmap { grid-template-columns: repeat(2, 1fr); }
    .f-hero-title { font-size: 17px; }
}
</style>""", unsafe_allow_html=True)
    if st.session_state.get("tma_theme") == "Dark":
        st.markdown(
            """
            <style>
            /* ── Dark mode: re-map ALL design tokens ── */
            :root {
                --tma-bg:           #0f172a !important;
                --tma-surface:      #1e293b !important;
                --tma-border:       #334155 !important;
                --tma-text:         #f1f5f9 !important;
                --tma-text-muted:   #94a3b8 !important;
                --tma-primary-light:#1e3a5f !important;
                --tma-shadow-sm:    0 1px 2px rgba(0,0,0,.4) !important;
                --tma-shadow-md:    0 4px 14px rgba(0,0,0,.5) !important;
                --tma-shadow-lg:    0 10px 30px rgba(0,0,0,.6) !important;
            }

            /* ── Base ── */
            html, body, [class*="css"], .stApp,
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            .main .block-container {
                background: #0f172a !important;
                background-image: none !important;
                color: #f1f5f9 !important;
            }

            /* ── Top nav bar ── */
            div.st-key-tma_topnav {
                background: #1e293b !important;
                border-bottom-color: #334155 !important;
                box-shadow: 0 1px 5px rgba(0,0,0,.4) !important;
            }
            div.st-key-tma_topnav button {
                background: #1e293b !important;
                color: #cbd5e1 !important;
                border-color: #334155 !important;
            }
            div.st-key-tma_topnav button:hover {
                background: #243245 !important;
                border-color: #60a5fa !important;
                color: #bfdbfe !important;
            }
            div.st-key-tma_topnav button[kind="primary"] {
                background: linear-gradient(135deg, #1d4ed8, #7c3aed) !important;
                color: #fff !important;
                border-color: transparent !important;
            }
            /* toggle label */
            div.st-key-tma_topnav label { color: #cbd5e1 !important; }

            /* ── Headings & text ── */
            h1, h2, h3, h4, h5, h6 { color: #f1f5f9 !important; }
            p, li, label, .stMarkdown, .stCaption { color: #cbd5e1 !important; }
            hr { border-color: #334155 !important; }
            a { color: #60a5fa !important; }

            /* ── Metric cards ── */
            div[data-testid="stMetric"] {
                background: #1e293b !important;
                border-color: #334155 !important;
            }
            div[data-testid="stMetricLabel"] { color: #94a3b8 !important; }

            /* ── Tabs ── */
            .stTabs [data-baseweb="tab-list"] {
                background: #0f172a !important;
                border-color: #334155 !important;
            }
            .stTabs [data-baseweb="tab"] {
                color: #94a3b8 !important;
                background: transparent !important;
            }
            .stTabs [data-baseweb="tab"]:hover { color: #60a5fa !important; }
            .stTabs [aria-selected="true"] {
                background: #1e293b !important;
                color: #60a5fa !important;
                box-shadow: 0 1px 4px rgba(0,0,0,.4) !important;
            }

            /* ── All regular buttons ── */
            .stButton > button {
                background: #1e293b !important;
                color: #e2e8f0 !important;
                border-color: #475569 !important;
            }
            .stButton > button:hover {
                background: #243245 !important;
                border-color: #60a5fa !important;
                color: #bfdbfe !important;
            }
            .stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
                color: #fff !important;
                border-color: transparent !important;
            }
            .stDownloadButton > button {
                background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
                color: #fff !important;
            }

            /* ── File uploader ── */
            [data-testid="stFileUploader"] {
                background: #1e293b !important;
                border-color: #475569 !important;
            }
            [data-testid="stFileUploader"]:hover { border-color: #60a5fa !important; }
            [data-testid="stFileUploader"] label,
            [data-testid="stFileUploader"] p,
            [data-testid="stFileUploader"] span { color: #cbd5e1 !important; }
            [data-testid="stFileUploader"] button {
                background: #1e293b !important;
                color: #e2e8f0 !important;
                border-color: #475569 !important;
            }

            /* ── Inputs (select, text, textarea, number) ── */
            .stSelectbox label, .stTextInput label, .stTextArea label,
            .stNumberInput label, .stCheckbox label, .stSlider label {
                color: #cbd5e1 !important;
            }
            .stSelectbox > div > div,
            .stTextInput > div > div,
            .stTextArea > div,
            .stNumberInput > div > div {
                background: #1e293b !important;
                border-color: #475569 !important;
                color: #f1f5f9 !important;
            }
            .stSelectbox > div > div > div,
            .stTextInput > div > div > input,
            .stTextArea > div > textarea,
            .stNumberInput > div > div > input {
                color: #f1f5f9 !important;
                background: #1e293b !important;
            }
            /* Dropdown menu */
            [data-baseweb="popover"] ul, [data-baseweb="menu"] {
                background: #1e293b !important;
                border-color: #334155 !important;
            }
            [data-baseweb="popover"] li, [data-baseweb="menu"] li { color: #f1f5f9 !important; }
            [data-baseweb="popover"] li:hover, [data-baseweb="menu"] li:hover {
                background: #243245 !important;
            }
            [data-testid="stCheckbox"] span { color: #cbd5e1 !important; }

            /* ── Alerts / banners ── */
            .stAlert {
                background: #1e293b !important;
                border-color: #334155 !important;
                color: #cbd5e1 !important;
            }
            [data-testid="stAlertContainer"] { background: #1e2d3d !important; }
            /* success banner (green) */
            [data-testid="stAlertContainer"][data-baseweb="notification"] {
                background: #052e16 !important;
                border-color: #166534 !important;
                color: #bbf7d0 !important;
            }

            /* ── Expanders ── */
            [data-testid="stExpander"] {
                background: #1e293b !important;
                border-color: #334155 !important;
            }
            [data-testid="stExpander"] summary { color: #f1f5f9 !important; }

            /* ── Data tables ── */
            [data-testid="stDataFrame"], .stDataFrame {
                background: #1e293b !important;
                border-color: #334155 !important;
            }
            [data-testid="stDataFrame"] th {
                background: #0f172a !important;
                color: #94a3b8 !important;
            }
            [data-testid="stDataFrame"] td { color: #cbd5e1 !important; }

            /* ── Progress bar ── */
            .stProgress > div > div { background: #334155 !important; }
            .stProgress > div > div > div { background: #22c55e !important; }

            /* ── Scrollbar ── */
            ::-webkit-scrollbar-track { background: #1e293b !important; }
            ::-webkit-scrollbar-thumb { background: #475569 !important; }

            /* ── TMA custom component classes ── */
            .tma-topnav {
                background: #1e293b !important;
                border-bottom-color: #334155 !important;
            }
            .tma-topnav-name { color: #f8fafc !important; }
            .tma-topnav-sub, .tma-nav-sub { color: #94a3b8 !important; }
            .tma-topnav-link { color: #94a3b8 !important; }
            .tma-topnav-link:hover { background: #243245 !important; color: #60a5fa !important; }
            .tma-topnav-link.active {
                background: #1e3a5f !important;
                color: #60a5fa !important;
                border-color: #3b82f6 !important;
            }
            .tma-topnav-status {
                background: #1e293b !important;
                border-color: #334155 !important;
                color: #94a3b8 !important;
            }
            .tma-nav-row { background: #1e293b !important; border-bottom-color: #334155 !important; }
            .tma-nav-brand { color: #f8fafc !important; }
            .tma-nav-status { color: #94a3b8 !important; }

            .tma-kpi-grid-item {
                background: #1e293b !important;
                border-color: #334155 !important;
            }
            .tma-kpi-label { color: #94a3b8 !important; }
            .tma-kpi-caption { color: #64748b !important; }

            .tma-panel {
                background: #1e293b !important;
                border-color: #334155 !important;
            }
            .tma-panel-header {
                background: #0f172a !important;
                border-bottom-color: #334155 !important;
            }
            .tma-panel-title { color: #f8fafc !important; }
            .tma-panel-subtitle { color: #94a3b8 !important; }
            .tma-panel-body { color: #cbd5e1 !important; }

            /* ── Inline hardcoded colours in render_topnav HTML ── */
            [style*="color:#0f172a"] { color: #f1f5f9 !important; }
            [style*="color:#64748b"] { color: #94a3b8 !important; }
            [style*="color:#475569"] { color: #94a3b8 !important; }
            [style*="background:#fafbfc"] { background: #1e293b !important; }
            [style*="background:#ffffff"] { background: #1e293b !important; }
            [style*="background:#fff"] { background: #1e293b !important; }
            [style*="border-color:#e2e8f0"] { border-color: #334155 !important; }
            </style>
            """,
            unsafe_allow_html=True,
        )


# ── PHASE 1 UI REFACTOR — Top Navigation Bar ──────────────────────────────────

# Page definitions: (page_key, display_label)
_NAV_PAGES = [
    ("home",                "Home"),
    ("command_center",      "Command Center"),
    ("version_converter",   "Version Converter"),  # hidden by default; toggled via Settings
    ("executive_dashboard", "Executive Dashboard"),
    ("portfolio",           "Portfolio Dashboard"),
    ("job_analysis",        "Job 360 Analysis"),
    ("repository_search",   "Repository Search"),  # hidden by default; toggled via Settings
    # ("tdd",              "Documentation"),  # merged into Job 360 > TDD tab
    # ("documentation_hub",   "Documentation"),  # merged into Job 360 > Docs Hub tab
    ("testing_architecture","Testing Architecture"),
    ("migration_advisor",   "Migration Advisor"),
    ("settings",            "Settings"),
]

# Pages hidden from nav by default; can be re-enabled via Settings
_HIDDEN_PAGES_DEFAULT = {"version_converter", "portfolio", "migration_advisor"}



def render_topnav() -> str:
    """Native Streamlit top navigation keyed by stable page ids."""
    _ALL_LABEL_KEYS = [k for k, _, _ in [
        ("home",                "🏠 Home",               "Upload · Scan · Analyse"),
        ("command_center",      "🔬 Analyse",            "Repository · Risks · Deps"),
        ("version_converter",   "🔄 Converter",          "6→7→8 · Batch · Advisor"),
        ("executive_dashboard", "📊 Executive",          "KPIs · RAG · Readiness"),
        ("portfolio",           "📁 Portfolio",          "Cross-repo · Status · Effort"),
        ("job_analysis",        "🔭 Job 360",             "Jobs · tMap · Java · Cloud"),
        ("repository_search",   "🔍 Search",             "Jobs · Tables · SQL · Contexts"),
        # ("documentation_hub",   "📄 Documentation",  # merged into Job 360
        ("testing_architecture","📋 Plan",               "Unit · SQL · Reconciliation"),
        ("migration_advisor",   "🧭 Migration Advisor",  "Target · Workflow · Roadmap"),
        ("settings",            "⚙️ Settings",           "Config · AI · Templates"),
    ]]
    _max_idx = len(_ALL_LABEL_KEYS) - 1
    try:
        current_idx = int(st.session_state.get("_nav_idx2", 0))
    except (TypeError, ValueError):
        current_idx = 0
    current_idx = max(0, min(current_idx, _max_idx))
    st.session_state["_nav_idx2"] = current_idx

    has_analysis = "last_analysis_jobs" in st.session_state
    job_count = len(st.session_state.get("last_analysis_jobs", []))
    status = f"✅ {job_count} jobs loaded" if has_analysis else "⬜ No repo"

    st.markdown("""
    <style>
    .block-container { padding-top: 76px !important; }
    div.st-key-tma_topnav {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 999999 !important;
        height: 72px !important;
        background: #ffffff !important;
        border-bottom: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 5px rgba(15, 23, 42, .08) !important;
        padding: 8px 16px !important;
    }
    div.st-key-tma_topnav div[data-testid="stHorizontalBlock"] {
        gap: 8px !important;
        align-items: center !important;
        flex-wrap: nowrap !important;
    }
    div.st-key-tma_topnav div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: 0 !important;
    }
    div.st-key-tma_topnav button {
        font-size: 11px !important;
        padding: 0.15rem 0.35rem !important;
        height: 30px !important;
        white-space: nowrap !important;
        min-width: 0 !important;
        width: 100% !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        box-sizing: border-box !important;
    }
    div.st-key-tma_topnav button * {
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }
    div.st-key-tma_topnav button p {
        font-size: 11px !important;
        margin: 0 !important;
    }
    @media (max-width: 1180px) {
        .block-container {
            padding-top: 98px !important;
        }
        div.st-key-tma_topnav {
            height: auto !important;
            min-height: 60px !important;
            padding-bottom: 10px !important;
        }
        div.st-key-tma_topnav div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        div.st-key-tma_topnav div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            flex: 1 1 120px !important;
            min-width: 110px !important;
        }
    }
    @media (max-width: 640px) {
        .block-container {
            padding-top: 144px !important;
        }
        div.st-key-tma_topnav div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
            flex: 1 1 46% !important;
            width: auto !important;
        }
        div.st-key-tma_topnav div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
            flex-basis: 100% !important;
        }
        div.st-key-tma_topnav div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
            display: none !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    _ALL_LABELS = [
        ("home",                "🏠 Home",               "Upload · Scan · Analyse"),
        ("command_center",      "🔬 Analyse",            "Repository · Risks · Deps"),
        ("version_converter",   "🔄 Converter",          "6→7→8 · Batch · Advisor"),
        ("executive_dashboard", "📊 Executive",          "KPIs · RAG · Readiness"),
        ("portfolio",           "📁 Portfolio",          "Cross-repo · Status · Effort"),
        ("job_analysis",        "🔭 Job 360",             "Jobs · tMap · Java · Cloud"),
        ("repository_search",   "🔍 Search",             "Jobs · Tables · SQL · Contexts"),
        # ("documentation_hub",   "📄 Documentation",  # merged into Job 360
        ("testing_architecture","📋 Plan",               "Unit · SQL · Reconciliation"),
        ("migration_advisor",   "🧭 Migration Advisor",  "Target · Workflow · Roadmap"),
        ("settings",            "⚙️ Settings",           "Config · AI · Templates"),
    ]

    # Determine which pages are hidden (session toggle overrides default)
    _hidden = set(st.session_state.get("_hidden_nav_pages", _HIDDEN_PAGES_DEFAULT))
    _LABELS = [(k, s, t) for k, s, t in _ALL_LABELS if k not in _hidden]

    # Remap current_idx to visible pages
    _all_keys = [k for k, _, _ in _ALL_LABELS]
    _vis_keys  = [k for k, _, _ in _LABELS]
    _cur_key   = _all_keys[current_idx] if current_idx < len(_all_keys) else "home"
    if _cur_key in _hidden:
        _cur_key = "home"
        st.session_state["_nav_idx2"] = 0
    _vis_idx = _vis_keys.index(_cur_key) if _cur_key in _vis_keys else 0

    _n = len(_LABELS)
    _BASE_BTN_WIDTHS = [0.8, 1.1, 0.85, 0.9, 1.15, 0.95, 0.85, 0.8, 0.75, 0.75, 0.75]
    _btn_widths = (_BASE_BTN_WIDTHS * ((_n // len(_BASE_BTN_WIDTHS)) + 1))[:_n]
    _col_widths = [1.3] + _btn_widths + [0.75, 1.0]

    _topnav = st.container(key="tma_topnav")
    with _topnav:
        _all_cols = st.columns(_col_widths)
        brand_col  = _all_cols[0]
        _btn_cols2 = _all_cols[1:_n+1]
        theme_col  = _all_cols[_n+1]
        status_col = _all_cols[_n+2]

        with brand_col:
            _logo_uri = _load_logo_data_uri()
            if _logo_uri:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;height:45px">'
                    f'<img src="{_logo_uri}" style="height:45px;max-height:45px;width:auto;'
                    f'object-fit:contain;background:#fff;border-radius:6px;padding:2px" '
                    f'alt="Artha logo"/>'
                    f'<div style="font-size:13px;font-weight:800;color:#0f172a">Artha Talend'
                    f'<div style="font-size:9px;color:#64748b;font-weight:500">Migration Accelerator</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="font-size:13px;font-weight:800;color:#0f172a;padding-top:2px">Artha Talend'
                    '<div style="font-size:9px;color:#64748b">Migration Accelerator</div></div>',
                    unsafe_allow_html=True,
                )

        _NAV_GROUPS_MAP = {
            "home": "Home", "command_center": "Analyse", "executive_dashboard": "Analyse",
            "portfolio": "Analyse", "job_analysis": "Explore", "repository_search": "Explore",
            "testing_architecture": "Plan", "migration_advisor": "Plan",
            "version_converter": "Plan", "settings": "Settings",
        }
        _prev_grp = None
        for i, (col, (page_key, short, tagline)) in enumerate(zip(_btn_cols2, _LABELS)):
            _cur_grp = _NAV_GROUPS_MAP.get(page_key)
            with col:
                is_active = (i == _vis_idx)
                btn_type = "primary" if is_active else "secondary"
                if st.button(short, key=f"nav2_{page_key}", type=btn_type, use_container_width=True):
                    # Store the global index for this page key
                    _gidx = _all_keys.index(page_key) if page_key in _all_keys else 0
                    st.session_state["_nav_idx2"] = _gidx
                    st.session_state["_advanced_page"] = None
                    st.rerun()
                tag_color = "#3b82f6" if is_active else "#94a3b8"
                tag_weight = "600" if is_active else "400"
                _prev_grp = _cur_grp  # track for group boundaries
                st.markdown(
                    f'<div style="font-size:8px;color:{tag_color};text-align:center;'
                    f'margin-top:-8px;white-space:nowrap;overflow:hidden;'
                    f'text-overflow:ellipsis;font-weight:{tag_weight};letter-spacing:0.02em;">'
                    f'{tagline}</div>',
                    unsafe_allow_html=True,
                )

        with theme_col:
            dark_on = st.session_state.get("tma_theme") == "Dark"
            # Use on_change so the theme toggle does NOT fire an extra rerun that
            # races with nav state and causes the wrong tab to flash momentarily.
            def _toggle_theme():
                st.session_state["tma_theme"] = (
                    "Dark" if st.session_state.get("tma_theme_toggle") else "Light"
                )
            st.toggle(
                "Dark",
                value=dark_on,
                key="tma_theme_toggle",
                label_visibility="collapsed",
                on_change=_toggle_theme,
            )

        with status_col:
            st.markdown(
                f'<div style="font-size:10px;color:#64748b;text-align:right;padding-top:6px">v3.0 · {status}</div>',
                unsafe_allow_html=True,
            )

    # Return the resolved page key directly — never index into _NAV_PAGES with
    # current_idx because that integer can lag by one rerun cycle when any widget
    # (theme toggle, popover, etc.) triggers a rerun before nav state settles,
    # causing the wrong tab (e.g. Command Center) to flash briefly.
    return _cur_key

# ── PHASE 1 UI REFACTOR — KPI Grid utility ────────────────────────────────────

def render_kpi_row(items: list[dict]) -> None:
    """
    PHASE 1 UI REFACTOR
    Render up to 4 KPI tiles in a single CSS grid row.

    Parameters
    ----------
    items : list of dict with keys:
        label   (str)  — uppercase metric label
        value   (str)  — prominent numeric/text value
        caption (str, optional) — small sub-text
        color   (str, optional) — hex colour for value text, default #1d4ed8
    """
    tiles_html = ""
    for item in items[:4]:
        label   = item.get("label", "")
        value   = item.get("value", "—")
        caption = item.get("caption", "")
        color   = item.get("color", "#1d4ed8")
        cap_html = f'<div class="tma-kpi-caption">{caption}</div>' if caption else ""
        tiles_html += (
            f'<div class="tma-kpi-grid-item">'
            f'<div class="tma-kpi-label">{label}</div>'
            f'<div class="tma-kpi-value" style="color:{color};">{value}</div>'
            f'{cap_html}</div>'
        )
    st.markdown(
        f'<div class="tma-kpi-grid">{tiles_html}</div>',
        unsafe_allow_html=True,
    )


def render_tab_skeleton(lines: int = 3, show_kpi: bool = True, show_block: bool = True) -> None:
    """
    Render an animated shimmer skeleton for a tab that is loading.

    Call this at the very top of a ``with tab:`` block, then clear it
    by writing over the same ``st.empty()`` placeholder — or simply let
    Streamlit replace it on the next rerun once real content renders.

    Parameters
    ----------
    lines      : number of text-line shimmer bars to show (default 3)
    show_kpi   : whether to include a 4-column KPI row shimmer
    show_block : whether to include a large block shimmer (e.g. chart/table)

    Usage
    -----
    with my_tab:
        _loading = st.empty()
        with _loading.container():
            render_tab_skeleton()
        # … compute expensive content …
        _loading.empty()          # clears skeleton
        st.markdown("Real content here")
    """
    kpi_row = ""
    if show_kpi:
        kpi_row = (
            '<div class="tma-skel-kpi-row">'
            + '<div class="tma-skel tma-skel-kpi"></div>' * 4
            + '</div>'
        )

    line_widths = ["w100", "w80", "w60", "w100", "w80"]
    line_html = "".join(
        f'<div class="tma-skel tma-skel-line {line_widths[i % len(line_widths)]}"></div>'
        for i in range(lines)
    )

    block_html = '<div class="tma-skel tma-skel-block"></div>' if show_block else ""

    st.markdown(
        f"""
        <div class="tma-tab-loading">
          <div class="tma-skel tma-skel-title"></div>
          {kpi_row}
          {line_html}
          {block_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── PHASE 1 UI REFACTOR — Fixed-Height Panel ──────────────────────────────────

_INTELLIGENT_KPIS = {
    "complexity",
    "migration risk",
    "migration effort",
    "cloud readiness",
    # ── Migration Review KPIs (Step 3) ──────────────────────────────────────
    "jobs",
    "readiness",
    "high risk",
    "est. weeks",
}


def _open_settings_button(key: str) -> None:
    if st.button("Open Settings", key=key, use_container_width=True):
        _settings_idx = next(
            (i for i, (k, _) in enumerate(_NAV_PAGES) if k == "settings"), 8
        )
        st.session_state["_nav_idx2"] = _settings_idx
        st.session_state["_advanced_page"] = None
        st.rerun()


def _settings_section_for_kpi(label: str) -> str:
    return {
        "complexity": "Complexity Scoring",
        "migration risk": "Migration Risk",
        "migration effort": "Effort Estimation",
        "cloud readiness": "Cloud Readiness",
        "jobs": "Scope & Inventory",
        "readiness": "Readiness Scoring",
        "high risk": "Risk Thresholds",
        "est. weeks": "Effort Estimation",
    }.get(str(label or "").strip().lower(), "Assessment Rules")


def _open_settings_section(label: str, key: str) -> None:
    if st.button("Open Settings", key=key, use_container_width=True):
        _si = next((i for i, (k, _) in enumerate(_NAV_PAGES) if k == "settings"), 8)
        st.session_state["settings_section"] = _settings_section_for_kpi(label)
        st.session_state["_nav_idx2"] = _si
        st.session_state["_advanced_page"] = None
        st.rerun()


def _open_simulation(key: str) -> None:
    if st.button("Simulate Changes", key=key, use_container_width=True):
        _si = next((i for i, (k, _) in enumerate(_NAV_PAGES) if k == "settings"), 8)
        st.session_state["settings_section"] = "Simulation Sandbox"
        st.session_state["_nav_idx2"] = _si
        st.session_state["_advanced_page"] = None
        st.rerun()


def _render_kpi_details(label: str, value, details: dict | None, key_prefix: str) -> None:
    """Render the popover body for an intelligent KPI badge.

    Design rules for editable widgets inside popovers
    -------------------------------------------------
    • Always call ``st.session_state.setdefault(key, initial)`` BEFORE rendering
      a widget so the stored value is used on every re-render (not the ``value=``
      argument, which would reset the widget each time the popover opens).
    • Read the persisted value from ``st.session_state[key]`` — never from the
      local ``details`` dict — after the first initialisation.
    • Buttons write their effect directly into canonical session-state keys and
      display ``st.success`` inline; they must NOT call ``st.rerun()`` inside a
      popover (it closes the popover).
    """
    import streamlit as _st  # local alias avoids shadowing module-level st
    details = details or {}
    normalized = str(label or "").strip().lower()

    # ── helper: initialise a session-state key once, then return its value ───
    def _ss(key: str, default):
        _st.session_state.setdefault(key, default)
        return _st.session_state[key]

    # ── helper: write a value to session state and return it -----------------
    def _save(key: str, val):
        _st.session_state[key] = val
        return val

    # ════════════════════════════════════════════════════════════════════════
    # Existing Job-360 KPIs (complexity / migration risk / effort / cloud)
    # ════════════════════════════════════════════════════════════════════════
    if normalized == "complexity":
        rows = details.get("components", {
            "Components":     details.get("component_score", "—"),
            "SQL Logic":      details.get("sql_logic",       "—"),
            "Dependencies":   details.get("dependencies",    "—"),
            "Custom Code":    details.get("custom_code",     "—"),
            "Migration Risk": details.get("migration_risk",  "—"),
        })
        st.markdown("**Migration Complexity Breakdown**")
        st.table([{"Component": k, "Score": v} for k, v in rows.items()])
        st.markdown(f"**Total Score:** {details.get('total_score', value)}")
        with st.expander("Thresholds", expanded=True):
            st.table([
                {"Level": "Low",       "Range": "0–40"},
                {"Level": "Medium",    "Range": "41–80"},
                {"Level": "High",      "Range": "81–120"},
                {"Level": "Very High", "Range": ">120"},
            ])

    elif normalized == "migration risk":
        st.markdown("**Unsupported Components**")
        for item in (details.get("unsupported_components") or
                     ["Custom Java", "External Scripts", "Legacy Components", "Dependencies"]):
            st.markdown(f"- {item}")
        st.markdown(f"**Risk Score:** {details.get('risk_score', value)}")
        st.markdown(f"**Risk Rating:** {details.get('risk_rating', value)}")

    elif normalized == "migration effort":
        rows = details.get("hours", {
            "Analysis Hours":     details.get("analysis_hours",      "—"),
            "SQL Conversion":     details.get("sql_conversion",      "—"),
            "Component Migration":details.get("component_migration", "—"),
            "Testing":            details.get("testing",             "—"),
            "Validation":         details.get("validation",          "—"),
        })
        st.table([{"Workstream": k, "Hours": v} for k, v in rows.items()])
        st.markdown(f"**Total Hours:** {details.get('total_hours', value)}")

    elif normalized == "cloud readiness":
        positive = details.get("positive") or ["Standard Components", "Metadata Driven"]
        negative = details.get("negative") or ["Custom Java", "Local Files", "Unsupported Components"]
        for item in positive:
            st.markdown(f"✓ {item}")
        for item in negative:
            st.markdown(f"✗ {item}")
        st.markdown(f"**Readiness Score:** {details.get('readiness_score', value)}")

    # ════════════════════════════════════════════════════════════════════════
    # Migration Review KPIs — Jobs / Readiness / High Risk / Est. Weeks
    # ════════════════════════════════════════════════════════════════════════

    elif normalized == "jobs":
        st.markdown("**Scope Breakdown**")
        st.table([
            {"Category": "Total jobs in repository",    "Value": details.get("total_jobs",      value)},
            {"Category": "In-scope for this migration", "Value": details.get("in_scope",         value)},
            {"Category": "Auto-migratable",             "Value": details.get("auto_migratable",  "—")},
            {"Category": "Require manual review",       "Value": details.get("manual_review",    "—")},
        ])
        st.markdown(
            "**What counts as 'in scope'?**  \n"
            "A job is in scope when it belongs to the selected Talend repository ZIP and targets the "
            "configured migration destination. Joblets and shared routines are counted separately. "
            "Adjust the scope filter in *Settings → Scope & Inventory* to exclude project folders or job types."
        )

    elif normalized == "readiness":
        rag_icon = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}.get(str(value).upper(), "⚪")
        st.markdown(f"**Overall Readiness:** {rag_icon} {value}")
        st.markdown(
            "Readiness is a composite score combining:\n"
            "- **Component compatibility** — how many components map cleanly to the target version\n"
            "- **Java custom code** — tJava / tJavaRow blocks need manual porting\n"
            "- **Deprecated usage** — components removed in the target version\n"
            "- **Risk density** — ratio of HIGH/CRITICAL findings per job\n\n"
            "| Status | Meaning |\n"
            "|--------|---------|\n"
            "| 🟢 GREEN | < 5 % of components need attention |\n"
            "| 🟡 AMBER | 5–25 % need review or rework |\n"
            "| 🔴 RED   | > 25 % require significant remediation |"
        )
        with st.expander("⚙️ Tune Readiness Thresholds", expanded=False):
            _k_green = f"readiness_green_ceiling"
            _k_amber = f"readiness_amber_ceiling"
            # Initialise from details or defaults — only on first render
            _ss(_k_green, details.get("green_ceiling", 5))
            _ss(_k_amber, details.get("amber_ceiling", 25))

            st.caption("Drag sliders to change the GREEN / AMBER boundary, then click Save.")
            new_green = st.slider(
                "GREEN ceiling (%)", 0, 50,
                st.session_state[_k_green],
                key=f"{key_prefix}_rs_green_widget",
            )
            new_amber = st.slider(
                "AMBER ceiling (%)", new_green + 1, 100,
                max(st.session_state[_k_amber], new_green + 1),
                key=f"{key_prefix}_rs_amber_widget",
            )
            if st.button("💾 Save Thresholds", key=f"{key_prefix}_rs_save"):
                _save(_k_green, new_green)
                _save(_k_amber, new_amber)
                st.success(
                    f"Saved — GREEN < {new_green}%, AMBER {new_green}–{new_amber}%, "
                    f"RED > {new_amber}%. Re-run analysis to recalculate."
                )

    elif normalized == "high risk":
        st.markdown(f"**{value} HIGH/CRITICAL finding(s)** must be resolved before migration.")
        st.markdown(
            "A finding is rated HIGH or CRITICAL when any of the following is detected:\n"
            "- **tJava / tJavaRow / tJavaFlex** — inline Java that cannot be auto-migrated\n"
            "- **Unsupported components** — components removed from the target version\n"
            "- **Deprecated APIs** — code calling methods no longer available\n"
            "- **Hardcoded credentials** — plain-text passwords in job parameters\n"
            "- **Missing context groups** — context variables referenced but undefined"
        )
        st.info("⚙️ To change which findings are flagged, go to **Settings → Migration Risk**.")

    elif normalized == "est. weeks":
        rows = details.get("breakdown", {
            "Discovery & scoping":  "—",
            "Component migration":  "—",
            "Java code porting":    "—",
            "Testing & QA":         "—",
            "UAT & sign-off":       "—",
        })
        st.markdown("**Effort Breakdown (weeks)**")
        st.table([{"Phase": k, "Weeks": v} for k, v in rows.items()])
        st.markdown(
            f"**Baseline total:** {value} week(s).  \n"
            "Estimate assumes a blended team of 1–2 ETL engineers. "
            "AI-assisted auto-fix can reduce effort by up to 30 %."
        )
        with st.expander("⚙️ Tune Effort Assumptions", expanded=False):
            _k_rate = "default_blended_rate"
            _k_ai   = "default_ai_reduction"
            _k_team = "default_team_size"
            _ss(_k_rate, details.get("blended_rate", 900))
            _ss(_k_ai,   details.get("ai_reduction",  30))
            _ss(_k_team, details.get("team_size", "2 engineers"))

            st.caption("Adjust assumptions then click Recalculate to update the estimate.")
            new_rate = st.number_input(
                "Blended daily rate ($)", 100, 5000,
                int(st.session_state[_k_rate]), step=50,
                key=f"{key_prefix}_ef_rate_widget",
            )
            new_ai = st.slider(
                "AI effort reduction (%)", 0, 60,
                int(st.session_state[_k_ai]),
                key=f"{key_prefix}_ef_ai_widget",
            )
            _team_opts = ["1 engineer", "2 engineers", "3+ engineers"]
            _team_idx  = _team_opts.index(st.session_state[_k_team]) if st.session_state[_k_team] in _team_opts else 1
            new_team = st.selectbox(
                "Team size", _team_opts, index=_team_idx,
                key=f"{key_prefix}_ef_team_widget",
            )
            if st.button("🔄 Recalculate Estimate", key=f"{key_prefix}_ef_recalc"):
                _save(_k_rate, new_rate)
                _save(_k_ai,   new_ai)
                _save(_k_team, new_team)
                st.success(
                    f"Assumptions saved — rate ${new_rate}/day, {new_ai}% AI reduction, {new_team}. "
                    "Regenerate reports to see updated estimates."
                )

    # ── Explain Score (all KPIs) ─────────────────────────────────────────────
    notes = details.get("notes") or "Score methodology and additional diagnostics will appear here."
    with st.expander("ℹ️ Explain Score", expanded=False):
        st.write(notes)

    # ── Bottom action row ────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        _open_settings_section(label, f"{key_prefix}_open_settings")
    with c2:
        _open_simulation(f"{key_prefix}_simulate_changes")


def render_kpi_badge(label: str, value, caption: str = "", color: str = "blue",
                     details: dict | None = None, key: str | None = None) -> None:
    """Render an interactive KPI badge with hover help and click popover."""
    normalized = str(label or "").strip().lower()
    if normalized not in _INTELLIGENT_KPIS:
        metric_card(label, value, caption, color)
        return

    help_text = f"{label}: click for breakdown, expandable details, and settings."
    pop_key = key or f"kpi_popover_{normalized.replace(' ', '_')}_{uuid.uuid4().hex}"
    pop_label = f"{label}: {value}"
    with st.popover(pop_label, help=help_text, use_container_width=True):
        if caption:
            st.caption(caption)
        _render_kpi_details(label, value, details, pop_key)


def render_kpi_row(items: list[dict]) -> None:
    """Render compact KPI tiles with native Streamlit metrics."""
    visible_items = items[:4]
    if not visible_items:
        return
    cols = st.columns(len(visible_items))
    for idx, (col, item) in enumerate(zip(cols, visible_items)):
        with col:
            label = item.get("label", "")
            value = item.get("value", "-")
            if str(label).strip().lower() in _INTELLIGENT_KPIS:
                render_kpi_badge(
                    label,
                    value,
                    item.get("caption", ""),
                    item.get("color", "blue"),
                    item.get("details"),
                    key=item.get("key") or f"kpi_row_{idx}_{str(label).lower().replace(' ', '_')}_{uuid.uuid4().hex}",
                )
            else:
                st.metric(
                    label=label,
                    value=value,
                    delta=item.get("caption") or None,
                    delta_color="off",
                )


def panel_open(title: str, subtitle: str = "", height: int = 360) -> None:
    """
    PHASE 1 UI REFACTOR
    Open a fixed-height scrollable panel card.
    Always pair with panel_close().

    Parameters
    ----------
    title    : panel header title
    subtitle : optional small subtitle in the header
    height   : inner body height in pixels (default 360)
    """
    sub_html = (
        f'<div class="tma-panel-subtitle">{subtitle}</div>' if subtitle else ""
    )
    st.markdown(
        f'<div class="tma-panel">'
        f'<div class="tma-panel-header">'
        f'<div><div class="tma-panel-title">{title}</div>{sub_html}</div>'
        f'</div>'
        f'<div class="tma-panel-body" style="max-height:{height}px;">',
        unsafe_allow_html=True,
    )


def panel_close() -> None:
    """PHASE 1 UI REFACTOR — Close a panel opened with panel_open()."""
    st.markdown("</div></div>", unsafe_allow_html=True)


# ── PHASE 1 UI REFACTOR — Compact Page Header ─────────────────────────────────

def page_header(icon: str, title: str, subtitle: str = "") -> None:
    """
    PHASE 1 UI REFACTOR
    Compact page header strip — replaces the larger section_header() banner
    used at the top of each routed page.

    Parameters
    ----------
    icon     : emoji or short string shown in a coloured box
    title    : page title (bold)
    subtitle : optional one-liner below the title
    """
    sub_html = (
        f'<div class="tma-page-header-sub">{subtitle}</div>' if subtitle else ""
    )
    st.markdown(
        f'<div class="tma-page-header">'
        f'<div class="tma-page-header-icon">{icon}</div>'
        f'<div>'
        f'<div class="tma-page-header-title">{title}</div>'
        f'{sub_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


# Alias kept for backward compatibility — several dashboard pages
# (migration_advisor_dashboard, migration_runbook_dashboard, etc.) import
# this name instead of page_header().
std_page_header = page_header


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ORIGINAL COMPONENT FUNCTIONS — unchanged from previous design_system_v2.py
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def sidebar_brand() -> None:
    """
    PHASE 1 UI REFACTOR — kept for import compatibility.
    Sidebar is hidden; this is a no-op.  Callers that previously called
    sidebar_brand() will continue to work without change.
    """
    pass  # sidebar is hidden in Phase 1


def sidebar_status(has_analysis: bool, job_count: int = 0) -> None:
    """
    PHASE 1 UI REFACTOR — kept for import compatibility.
    Status is now rendered inside render_topnav().  This is a no-op.
    """
    pass


def topbar(subtitle: str = "") -> None:
    """
    PHASE 1 UI REFACTOR — kept for import compatibility.
    Page-level context subtitle is now shown via page_header().
    This renders a minimal inline subtitle so existing call sites don't break.
    """
    if subtitle:
        st.markdown(
            f'<div style="font-size:11px;color:#64748b;margin:-6px 0 8px;">{subtitle}</div>',
            unsafe_allow_html=True,
        )


def wizard_progress(current_step: int) -> None:
    """Numbered stepper with connecting lines — completed steps fill blue."""
    steps = ["Upload", "Analyze", "Review", "Generate", "Download"]
    current_step = max(1, min(int(current_step), len(steps)))
    n = len(steps)

    # Build one flex row: [dot+label] [line] [dot+label] …
    items_html = ""
    for i, label in enumerate(steps, start=1):
        done    = i < current_step
        active  = i == current_step
        pending = i > current_step

        # Circle
        if done:
            circle_bg  = "#1d4ed8"
            circle_fg  = "#ffffff"
            circle_border = "#1d4ed8"
            circle_inner  = "✓"
            label_color   = "#1d4ed8"
            label_weight  = "700"
        elif active:
            circle_bg  = "#1d4ed8"
            circle_fg  = "#ffffff"
            circle_border = "#1d4ed8"
            circle_inner  = str(i)
            label_color   = "#0f172a"
            label_weight  = "700"
        else:
            circle_bg  = "#ffffff"
            circle_fg  = "#94a3b8"
            circle_border = "#cbd5e1"
            circle_inner  = str(i)
            label_color   = "#94a3b8"
            label_weight  = "500"

        # Active ring glow
        box_shadow = "0 0 0 4px #bfdbfe" if active else "none"

        step_html = (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:5px;flex:0 0 auto;">'
            f'<div style="width:32px;height:32px;border-radius:50%;background:{circle_bg};'
            f'color:{circle_fg};border:2px solid {circle_border};display:flex;align-items:center;'
            f'justify-content:center;font-size:12px;font-weight:700;box-shadow:{box_shadow};'
            f'transition:all .2s ease;">{circle_inner}</div>'
            f'<span style="font-size:11px;font-weight:{label_weight};color:{label_color};'
            f'white-space:nowrap;">{label}</span>'
            f'</div>'
        )

        items_html += step_html

        # Connector line between steps (not after last)
        if i < n:
            line_color = "#1d4ed8" if done else "#e2e8f0"
            items_html += (
                f'<div style="flex:1;height:2px;background:{line_color};'
                f'margin-bottom:18px;min-width:24px;transition:background .3s;"></div>'
            )

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:0;padding:12px 8px 4px;'
        f'background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:16px;">'
        + items_html +
        f'</div>',
        unsafe_allow_html=True,
    )




def page_title(step_num: int, title: str, subtitle: str = "") -> None:
    """Unchanged from design_system_v2 — wizard step title."""
    st.markdown(
        f'<div style="margin-bottom:8px;">'
        f'<div style="font-size:18px;font-weight:800;color:#0f172a;">{title}</div></div>',
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """Unchanged from design_system_v2 — section divider with optional subtitle."""
    st.markdown(
        f'<div style="margin:8px 0 5px;">'
        f'<div style="font-size:14px;font-weight:700;color:#0f172a;">{title}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def RepositoryOverviewCard(overview) -> None:
    """
    Render the repository-level overview card.

    Parameters
    ----------
    overview : app.analyzers.models.RepositoryOverview (or dict with the
        same keys produced by RepositoryOverview.to_dict()).
    """
    data = overview.to_dict() if hasattr(overview, "to_dict") else dict(overview)

    section_header("Repository Overview")

    repo_type = data.get("repositoryType", "Unknown")
    source_version = data.get("sourceVersion", "UNKNOWN")
    enterprise_features = data.get("enterpriseFeatures", [])
    features_label = ", ".join(enterprise_features) if enterprise_features else "None detected"
    target_versions = data.get("targetVersions", [])
    targets_label = ", ".join(target_versions) if target_versions else "None available"
    migration_risk = data.get("migrationRisk", "LOW")
    upgrade_path_summary = data.get("upgradePathSummary", "")

    _risk_color = {"CRITICAL": "#991b1b", "HIGH": "#b91c1c", "MEDIUM": "#b45309", "LOW": "#15803d"}.get(migration_risk, "#15803d")

    st.markdown(
        f'<div style="display:flex;gap:18px;flex-wrap:wrap;margin:2px 0 10px;'
        f'font-size:13px;color:#334155;">'
        f'<div><b>Repository Type:</b> {repo_type}</div>'
        f'<div><b>Source Version:</b> {source_version}</div>'
        f'<div><b>Enterprise Features:</b> {features_label}</div>'
        f'<div><b>Supported Target Versions:</b> {targets_label}</div>'
        f'<div><b>Migration Risk:</b> '
        f'<span style="color:{_risk_color};font-weight:700;">{migration_risk}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if upgrade_path_summary:
        st.markdown(
            f'<div style="font-size:13px;color:#475569;margin:0 0 10px;">'
            f'<b>Upgrade Path Summary:</b> {upgrade_path_summary}</div>',
            unsafe_allow_html=True,
        )

    render_kpi_row([
        {"label": "Jobs", "value": str(data.get("totalJobs", 0)), "caption": "In scope", "color": "#1d4ed8"},
        {"label": "Joblets", "value": str(data.get("totalJoblets", 0)), "caption": "Reusable units", "color": "#0f766e"},
        {"label": "Routines", "value": str(data.get("totalRoutines", 0)), "caption": "Shared code", "color": "#6d28d9"},
        {"label": "Components", "value": str(data.get("totalComponents", 0)), "caption": "Runtime assets", "color": "#b45309"},
    ])
    render_kpi_row([
        {"label": "Complexity", "value": f"{data.get('complexityScore', 0)}%", "color": "#b45309"},
        {"label": "Migration Readiness", "value": f"{data.get('migrationReadinessScore', 0)}%", "color": "#15803d"},
        {"label": "Cloud Readiness", "value": f"{data.get('cloudReadinessScore', 0)}%", "color": "#0f766e"},
        {"label": "Testing Readiness", "value": f"{data.get('testingReadinessScore', 0)}%", "color": "#6d28d9"},
    ])


def ExecutiveDashboardCard(dashboard, mrs: dict | None = None) -> str | None:
    """
    Render the Executive Dashboard's KPI strip (Total Jobs · Analyzed ·
    Ready · Warning · High Risk · Failed · Status · Automation · Hours ·
    Risk · Migration Readiness Score) bound to an ExecutiveDashboard model
    and an optional MigrationReadinessScore dict (mrs).

    Parameters
    ----------
    dashboard : app.analyzers.models.ExecutiveDashboard (or dict with the
        same keys produced by ExecutiveDashboard.to_dict()).
    mrs : dict produced by MigrationReadinessScore.to_dict(), optional.

    Returns
    -------
    The active drilldown filter (str) if a KPI card was clicked, else None.
    """
    data = dashboard.to_dict() if hasattr(dashboard, "to_dict") else dict(dashboard)

    overall = data.get("cloudReadinessStatus", "RED")
    auto_pct = data.get("automationPct", 0)
    est_hours = data.get("estimatedHours", 0) or "—"
    est_weeks = data.get("estimatedWeeks", "—")
    high_risk = data.get("highRiskCount", 0)
    risk_label = data.get("riskLabel", "LOW")
    total = data.get("totalJobs", 0)
    total_comp = data.get("totalComponents", 0)

    status_color = "#15803d" if overall == "GREEN" else ("#b45309" if overall == "AMBER" else "#be123c")
    risk_color = "#be123c" if high_risk else ("#b45309" if risk_label == "MEDIUM" else "#15803d")

    analyzed_jobs = data.get("analyzedJobs", 0)
    ready_jobs = data.get("readyJobs", 0)
    warning_jobs = data.get("warningJobs", 0)
    failed_jobs = data.get("failedJobs", 0)

    kpi_items = [
        {"label": "Total Jobs", "value": str(total), "caption": f"{total_comp} components", "filter": "Total Jobs", "color": "#1d4ed8"},
        {"label": "Analyzed Jobs", "value": str(analyzed_jobs), "caption": f"of {total} jobs", "filter": "Analyzed Jobs", "color": "#0369a1"},
        {"label": "Ready Jobs", "value": str(ready_jobs), "caption": "cloud-ready (GREEN)", "filter": "Ready Jobs", "color": "#15803d"},
        {"label": "Warning Jobs", "value": str(warning_jobs), "caption": "needs review (AMBER)", "filter": "Warning Jobs", "color": "#b45309"},
        {"label": "High Risk Jobs", "value": str(high_risk), "caption": "HIGH/CRITICAL findings", "filter": "High Risk Jobs", "color": "#be123c"},
        {"label": "Failed Jobs", "value": str(failed_jobs), "caption": "blocked (RED)", "filter": "Failed Jobs", "color": "#7f1d1d"},
        {"label": "Readiness Status", "value": overall, "caption": "GREEN Low Effort / AMBER Medium Effort / RED High Effort", "filter": "Status", "color": status_color},
        {"label": "Automation", "value": f"{auto_pct}%", "caption": "auto-migratable", "filter": "Automation", "color": "#0f766e"},
        {"label": "Hours", "value": str(est_hours), "caption": f"{est_weeks} wks", "filter": "Hours", "color": "#6d28d9"},
        {"label": "Risk", "value": risk_label, "caption": f"{high_risk} high/critical", "filter": "Risk", "color": risk_color},
    ]

    if mrs:
        mrs_score = mrs.get("overallScore", 0)
        mrs_rag = mrs.get("overallRag", "RED")
        mrs_status = mrs.get("status", "NO DATA")
        mrs_color = "#15803d" if mrs_rag == "GREEN" else ("#b45309" if mrs_rag == "AMBER" else "#be123c")
        kpi_items.append({
            "label": "Migration Readiness Score", "value": f"{mrs_score}%",
            "caption": mrs_status, "filter": "Migration Readiness Score", "color": mrs_color,
        })

    return render_clickable_kpi_row(kpi_items, "kpi_filter", "exec_kpi")


def render_insights_row(insights: list[dict]) -> None:
    """
    Render an Intelligent Insights panel.
    Each insight dict: {icon, label, value, sub, color}
      icon   : emoji
      label  : short heading
      value  : bold highlighted text (e.g. "7 of 9 findings")
      sub    : smaller sub-line beneath
      color  : accent hex (#15803d / #b45309 / #1d4ed8)
    """
    if not insights:
        return
    items_html = ""
    for ins in insights:
        color = ins.get("color", "#1d4ed8")
        bg = color + "18"  # ~9% opacity background
        items_html += (
            f'<div style="display:flex;align-items:flex-start;gap:10px;padding:10px 14px;'
            f'background:{bg};border-left:3px solid {color};border-radius:8px;">'
            f'<span style="font-size:20px;line-height:1;">{ins.get("icon","💡")}</span>'
            f'<div>'
            f'<div style="font-size:12px;font-weight:700;color:{color};">{ins.get("label","")}</div>'
            f'<div style="font-size:13px;font-weight:600;color:#0f172a;margin-top:1px;">{ins.get("value","")}</div>'
            f'<div style="font-size:11px;color:#64748b;margin-top:2px;">{ins.get("sub","")}</div>'
            f'</div></div>'
        )
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;margin-bottom:10px;">'
        f'<div style="font-size:12px;font-weight:700;color:#64748b;letter-spacing:.06em;text-transform:uppercase;margin-bottom:10px;">💡 Intelligent Insights</div>'
        f'<div style="display:flex;flex-direction:column;gap:8px;">{items_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


_COMPLEXITY_COLORS = {
    "LOW": "#38a169", "MEDIUM": "#d69e2e",
    "HIGH": "#dd6b20", "CRITICAL": "#e53e3e",
}
_COMPLEXITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def complexity_breakdown_from_jobs(all_jobs: list) -> dict:
    """Derive a {LOW/MEDIUM/HIGH/CRITICAL: count} breakdown directly from a
    list of job dicts (each with an 'estimation' dict containing
    'complexity'). Jobs without a recognised complexity are skipped."""
    breakdown = {k: 0 for k in _COMPLEXITY_ORDER}
    for j in all_jobs or []:
        c = (j.get("estimation", {}) or {}).get("complexity")
        if c in breakdown:
            breakdown[c] += 1
    return breakdown


def render_complexity_distribution_chart(
    by_complexity: dict = None,
    all_jobs: list = None,
    chart_type: str = "pie",
    title: str = None,
    height: int = 220,
    key: str = "complexity_distribution_chart",
) -> None:
    """
    Render the portfolio Complexity Distribution chart (LOW/MEDIUM/HIGH/
    CRITICAL job counts) as a pie or bar chart.

    Parameters
    ----------
    by_complexity : dict {complexity_label: count}, e.g. effort_estimate's
        "by_complexity" field. Takes priority over all_jobs if both given.
    all_jobs : list of job dicts; used to derive the breakdown via
        complexity_breakdown_from_jobs() when by_complexity is not supplied.
    chart_type : "pie" (default) or "bar".
    title : optional chart title rendered above the figure.
    height : chart height in pixels.
    key : Streamlit widget key (must be unique per call site).
    """
    import plotly.express as px

    data = dict(by_complexity) if by_complexity else complexity_breakdown_from_jobs(all_jobs)
    data = {k: v for k, v in data.items() if v}

    if title:
        st.markdown(
            f'<div style="font-size:12px;font-weight:700;color:#64748b;'
            f'letter-spacing:.06em;text-transform:uppercase;margin-bottom:6px;">{title}</div>',
            unsafe_allow_html=True,
        )

    if not data or sum(data.values()) == 0:
        st.caption("Complexity chart — run analysis first.")
        return

    labels = [k for k in _COMPLEXITY_ORDER if k in data] or list(data.keys())
    values = [data[k] for k in labels]
    colors = [_COMPLEXITY_COLORS.get(k, "#64748b") for k in labels]

    if chart_type == "bar":
        fig = px.bar(
            x=labels, y=values, color=labels,
            color_discrete_sequence=colors,
            color_discrete_map=_COMPLEXITY_COLORS,
            labels={"x": "Complexity", "y": "Jobs"},
        )
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title=None)
        fig.update_yaxes(title=None)
    else:
        fig = px.pie(
            names=labels, values=values,
            color=labels,
            color_discrete_map=_COMPLEXITY_COLORS,
        )
        fig.update_traces(textfont_size=11)

    fig.update_layout(height=height, margin=dict(t=10, b=0, l=0, r=0),
                       showlegend=True, legend=dict(font_size=11))
    st.plotly_chart(fig, use_container_width=True, key=key)


def render_progress_metric(label: str, value: str, pct: int, caption: str = "", color: str = "#2563eb") -> None:
    """Render a metric card with an inline progress bar."""
    pct = max(0, min(100, int(pct)))
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;margin-bottom:6px;">'
        f'<div style="font-size:11px;color:#64748b;font-weight:600;">{label}</div>'
        f'<div style="font-size:1.4rem;font-weight:800;color:#0f172a;line-height:1.2;">{value}</div>'
        f'<div style="background:#e2e8f0;border-radius:4px;height:5px;margin-top:6px;">'
        f'<div style="background:{color};width:{pct}%;height:5px;border-radius:4px;"></div>'
        f'</div>'
        f'<div style="font-size:11px;color:#64748b;margin-top:3px;">{caption}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def get_rag_status(score: int, metric_type: str = "readiness") -> tuple[str, str, str, str]:
    """
    Convert a numeric score to RAG status.
    Returns (label, bg_color, border_color, text_color).
    metric_type: 'readiness' or 'cloud'
    """
    if score >= 75:
        return ("🟢 Cloud Ready", "#f0fdf4", "#86efac", "#15803d")
    elif score >= 50:
        return ("🟡 Remediation Required", "#fffbeb", "#fcd34d", "#b45309")
    else:
        return ("🔴 Significant Rework", "#fff1f2", "#fda4af", "#be123c")


def rag_badge(score: int) -> str:
    """Return inline HTML badge for RAG status (no st.markdown call)."""
    label, bg, border, fg = get_rag_status(score)
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:20px;'
        f'background:{bg};border:1px solid {border};color:{fg};'
        f'font-size:12px;font-weight:700;">{label}</span>'
    )


def rag_metric_card(label: str, score: int, caption: str = "") -> None:
    """KPI tile showing RAG status badge instead of a percentage."""
    rag_label, bg, border, fg = get_rag_status(score)
    cap = (
        f'<div style="font-size:11px;color:#64748b;margin-top:5px;">{caption}</div>'
        if caption else ""
    )
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;'
        f'border-top:3px solid {fg};padding:14px 16px;">'
        f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.06em;color:#64748b;">{label}</div>'
        f'<div style="margin-top:8px;">'
        f'<span style="display:inline-block;padding:4px 12px;border-radius:20px;'
        f'background:{bg};border:1px solid {border};color:{fg};'
        f'font-size:13px;font-weight:700;">{rag_label}</span>'
        f'</div>{cap}</div>',
        unsafe_allow_html=True,
    )


def migration_impact_card(
    status: str,
    migration_hours: int | float,
    custom_routines: int,
    unsupported_components: int,
    java_dependencies: int,
) -> None:
    """
    Compact executive Migration Impact Assessment card.

    Parameters
    ----------
    status                : str  — e.g. 'High Risk', 'Remediation Required', 'Cloud Ready'
    migration_hours       : int  — total estimated migration hours
    custom_routines       : int  — number of custom routines detected
    unsupported_components: int  — count of components not supported in target
    java_dependencies     : int  — number of jobs with Java risk
    """
    # Status colour
    _status_lower = status.lower()
    if "ready" in _status_lower or "low" in _status_lower:
        s_bg, s_bd, s_fg, s_icon = "#f0fdf4", "#86efac", "#15803d", "🟢"
    elif "high" in _status_lower or "critical" in _status_lower or "rework" in _status_lower:
        s_bg, s_bd, s_fg, s_icon = "#fff1f2", "#fda4af", "#be123c", "🔴"
    else:
        s_bg, s_bd, s_fg, s_icon = "#fffbeb", "#fcd34d", "#b45309", "🟡"

    def _kpi(label, value, icon=""):
        icon_span = f'<span style="font-size:15px;margin-right:5px;">{icon}</span>' if icon else ""
        return (
            f'<div style="flex:1;min-width:110px;background:#f8fafc;border:1px solid #e2e8f0;'
            f'border-radius:8px;padding:10px 12px;text-align:center;">'
            f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.06em;color:#64748b;margin-bottom:4px;">{label}</div>'
            f'<div style="font-size:20px;font-weight:800;color:#0f172a;line-height:1;">'
            f'{icon_span}{value}</div></div>'
        )

    kpis_html = (
        _kpi("Migration Hours", f"{migration_hours:,}", "⏱") +
        _kpi("Custom Routines", custom_routines, "📋") +
        _kpi("Unsupported Components", unsupported_components, "⚠️") +
        _kpi("Java Dependencies", java_dependencies, "☕")
    )

    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;'
        f'border-left:4px solid {s_fg};padding:16px 18px;margin:10px 0;">'
        # Header row
        f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">'
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.08em;color:#64748b;">Migration Impact Assessment</div>'
        f'<span style="display:inline-block;padding:3px 11px;border-radius:20px;'
        f'background:{s_bg};border:1px solid {s_bd};color:{s_fg};'
        f'font-size:12px;font-weight:700;">{s_icon} {status}</span>'
        f'</div>'
        # KPI tiles row
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;">{kpis_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def metric_card(
    label: str, value: str, caption: str = "", color: str = "blue"
) -> None:
    """Unchanged from design_system_v2 — single KPI tile."""
    clr = {
        "blue":   "#1d4ed8",
        "green":  "#15803d",
        "red":    "#be123c",
        "amber":  "#b45309",
        "purple": "#6d28d9",
        "teal":   "#0d7377",
        "gray":   "#475569",
    }.get(color, "#1d4ed8")
    cap = (
        f'<div style="font-size:11px;color:#64748b;margin-top:3px;">{caption}</div>'
        if caption else ""
    )
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;'
        f'border-top:3px solid {clr};padding:14px 16px;">'
        f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.06em;color:#64748b;">{label}</div>'
        f'<div style="font-size:26px;font-weight:800;color:{clr};'
        f'margin-top:4px;line-height:1.1;">{value}</div>{cap}</div>',
        unsafe_allow_html=True,
    )


def status_card(title: str, body: str, status: str = "info") -> None:
    """Unchanged from design_system_v2 — coloured status / info card."""
    p = {
        "info":    ("#4a78c4", "#f0f5ff", "#c3d4f5"),
        "success": ("#3d8a5c", "#f0faf5", "#9fd4b8"),
        "warning": ("#b87d3a", "#fef9f0", "#f0d49a"),
        "error":   ("#b85070", "#fff3f6", "#f0b4c0"),
    }.get(status, ("#4a78c4", "#f0f5ff", "#c3d4f5"))
    fg, bg, bd = p
    st.markdown(
        f'<div style="background:{bg};border:1px solid {bd};border-left:4px solid {fg};'
        f'border-radius:9px;padding:11px 14px;margin:5px 0;">'
        f'<div style="font-size:13px;font-weight:700;color:{fg};">{title}</div>'
        f'<div style="font-size:12px;color:#334155;margin-top:3px;'
        f'line-height:1.5;">{body}</div></div>',
        unsafe_allow_html=True,
    )


def success_banner(title: str, body: str) -> None:
    """Unchanged from design_system_v2 — blue success banner."""
    st.markdown(
        f'<div style="background:#1d4ed8;border-radius:12px;padding:20px 24px;'
        f'margin-bottom:16px;color:#fff;">'
        f'<div style="font-size:16px;font-weight:800;margin-bottom:4px;">✅ {title}</div>'
        f'<div style="font-size:12px;opacity:.9;line-height:1.5;">{body}</div></div>',
        unsafe_allow_html=True,
    )


_RAG_BANNER_STYLE = {
    "GREEN": ("#f0fdf4", "#86efac", "#15803d", "🟢"),
    "AMBER": ("#fffbeb", "#fcd34d", "#b45309", "🟡"),
    "RED":   ("#fff1f2", "#fda4af", "#be123c", "🔴"),
}


def render_rag_banner(rag: str, title: str = "Migration Readiness", subtitle: str = "") -> None:
    """Full-width RAG (RED / AMBER / GREEN) status banner.

    Parameters
    ----------
    rag      : "RED" | "AMBER" | "GREEN" — e.g. readiness_score["overall"]
    title    : banner heading (default "Migration Readiness")
    subtitle : optional small sub-text below the heading
    """
    bg, border, fg, icon = _RAG_BANNER_STYLE.get((rag or "").upper(), _RAG_BANNER_STYLE["RED"])
    sub_html = (
        f'<div style="font-size:12px;color:{fg};opacity:.85;margin-top:2px;">{subtitle}</div>'
        if subtitle else ""
    )
    st.markdown(
        f'<div style="background:{bg};border:1px solid {border};border-left:5px solid {fg};'
        f'border-radius:10px;padding:14px 18px;margin-bottom:14px;">'
        f'<div style="font-size:15px;font-weight:800;color:{fg};">'
        f'{icon} {title} — {(rag or "—").upper()}</div>'
        f'{sub_html}</div>',
        unsafe_allow_html=True,
    )


def download_card(icon: str, title: str, description: str) -> None:
    """Unchanged from design_system_v2 — download tile header."""
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;'
        f'padding:12px 14px 6px;margin-bottom:4px;">'
        f'<div style="font-size:20px;margin-bottom:4px;">{icon}</div>'
        f'<div style="font-size:13px;font-weight:600;color:#0f172a;">{title}</div>'
        f'<div style="font-size:11px;color:#64748b;margin-top:2px;">'
        f'{description}</div></div>',
        unsafe_allow_html=True,
    )


def render_job_hierarchy_tree(all_jobs: list) -> None:
    """
    Render an expandable Job Hierarchy tree.

    Master jobs (no parent) get their own st.expander.
    Each expander shows child jobs as an ASCII tree.
    Orphan children (referenced but not in the repo) are shown with a ⚠ badge.
    Standalone jobs (no children, no parent) are listed in a collapsed group.

    Parameters
    ----------
    all_jobs : list of parsed job dicts (standard TMA format)
    """
    # ── Build lookup ────────────────────────────────────────────────────────
    job_names   = {j["job_data"]["job_name"] for j in all_jobs}
    job_meta    = {j["job_data"]["job_name"]: j for j in all_jobs}

    # Map: parent → [children]
    parent_map: dict[str, list[str]] = {}
    # Set of all jobs that appear as a child somewhere
    is_child: set[str] = set()

    for j in all_jobs:
        jname    = j["job_data"]["job_name"]
        children = j.get("dependencies", {}).get("child_jobs", [])
        if children:
            parent_map[jname] = children
            is_child.update(children)

    masters    = [n for n in job_names if n not in is_child and n in parent_map]
    standalone = [n for n in job_names if n not in is_child and n not in parent_map]
    masters.sort()
    standalone.sort()

    # ── Helper: badge HTML ───────────────────────────────────────────────────
    def _complexity_badge(job_name: str) -> str:
        meta  = job_meta.get(job_name, {})
        cplx  = meta.get("estimation", {}).get("complexity", "")
        cloud = meta.get("cloud_readiness", {}).get("readiness", "")
        parts = []
        if cplx:
            c = {"LOW": "#15803d", "MEDIUM": "#b45309",
                 "HIGH": "#be123c", "CRITICAL": "#be123c"}.get(cplx, "#64748b")
            parts.append(
                f'<span style="background:{c}22;color:{c};border:1px solid {c}66;'
                f'border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;">'
                f'{cplx}</span>'
            )
        if cloud:
            c = {"HIGH": "#15803d", "MEDIUM": "#b45309", "LOW": "#be123c"}.get(cloud, "#64748b")
            lbl = {"HIGH": "☁ Ready", "MEDIUM": "☁ Partial", "LOW": "☁ Blocker"}.get(cloud, cloud)
            parts.append(
                f'<span style="background:{c}22;color:{c};border:1px solid {c}66;'
                f'border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;">'
                f'{lbl}</span>'
            )
        return "&nbsp;".join(parts)

    def _orphan_badge() -> str:
        return (
            '<span style="background:#fff1f2;color:#be123c;border:1px solid #fda4af;'
            'border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;">⚠ Not in repo</span>'
        )

    def _node_row(name: str, prefix: str, is_last: bool, depth: int = 1) -> str:
        """Return one HTML row for a tree node."""
        connector  = "└─" if is_last else "├─"
        mono_style = (
            "font-family:monospace;font-size:13px;color:#0f172a;"
            "white-space:pre;line-height:1.8;"
        )
        badges = _complexity_badge(name) if name in job_names else _orphan_badge()
        return (
            f'<div style="{mono_style}padding-left:{depth * 8}px;">'
            f'{prefix}{connector} <strong>{name}</strong>'
            f'&nbsp;&nbsp;{badges}</div>'
        )

    def _build_subtree(children: list[str], prefix: str = "", depth: int = 1) -> str:
        html = ""
        for i, child in enumerate(children):
            is_last    = (i == len(children) - 1)
            html      += _node_row(child, prefix, is_last, depth)
            # Recurse if child is also a parent
            grandchildren = parent_map.get(child, [])
            if grandchildren:
                next_prefix = prefix + ("    " if is_last else "│   ")
                html += _build_subtree(grandchildren, next_prefix, depth + 1)
        return html

    # ── Summary header ───────────────────────────────────────────────────────
    total_deps = sum(len(v) for v in parent_map.values())
    st.markdown(
        f'<div style="display:flex;gap:16px;margin-bottom:10px;">'
        f'<span style="font-size:12px;color:#64748b;">🏗 <strong>{len(masters)}</strong> master jobs</span>'
        f'<span style="font-size:12px;color:#64748b;">🔗 <strong>{total_deps}</strong> child dependencies</span>'
        f'<span style="font-size:12px;color:#64748b;">📦 <strong>{len(standalone)}</strong> standalone jobs</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not masters and not standalone:
        empty_state_card("No job hierarchy data available", "Run analysis first.")
        return

    # ── Master job expanders ─────────────────────────────────────────────────
    for master in masters:
        children    = parent_map.get(master, [])
        child_count = len(children)
        complexity  = job_meta.get(master, {}).get("estimation", {}).get("complexity", "")
        header_icon = "🟠" if complexity in ("HIGH", "CRITICAL") else "🟢"

        with st.expander(
            f"{header_icon} **{master}** — {child_count} child job{'s' if child_count != 1 else ''}",
            expanded=False,
        ):
            # Master node row
            master_badges = _complexity_badge(master)
            st.markdown(
                f'<div style="font-family:monospace;font-size:13px;font-weight:700;'
                f'color:#1d4ed8;line-height:2;">'
                f'📁 {master}&nbsp;&nbsp;{master_badges}</div>',
                unsafe_allow_html=True,
            )
            # Children tree
            tree_html = _build_subtree(children)
            st.markdown(
                f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                f'border-radius:8px;padding:10px 14px;margin-top:4px;">'
                f'{tree_html}</div>',
                unsafe_allow_html=True,
            )
            # Quick stats row
            comp_count = len(job_meta.get(master, {}).get("job_data", {}).get("components", []))
            est_hours  = job_meta.get(master, {}).get("estimation", {}).get("estimated_hours", "—")
            st.caption(f"Components: {comp_count} · Estimated: {est_hours}h · Children: {child_count}")

    # ── Standalone jobs (collapsed) ──────────────────────────────────────────
    if standalone:
        with st.expander(f"📦 Standalone Jobs ({len(standalone)} — no dependencies)", expanded=False):
            rows_html = "".join(
                f'<div style="font-family:monospace;font-size:12px;color:#475569;'
                f'line-height:1.9;padding-left:8px;">• <strong>{n}</strong>'
                f'&nbsp;&nbsp;{_complexity_badge(n)}</div>'
                for n in standalone
            )
            st.markdown(
                f'<div style="background:#f8fafc;border:1px solid #e2e8f0;'
                f'border-radius:8px;padding:10px 14px;">{rows_html}</div>',
                unsafe_allow_html=True,
            )


def render_unsupported_components_report(report: dict) -> None:
    """
    Render the Unsupported Components report in the dashboard.

    Parameters
    ----------
    report : output of analyze_unsupported_components()
    """
    if not report:
        empty_state_card("No unsupported component data available", "Run analysis first.")
        return

    summary  = report.get("summary", {})
    cats     = report.get("categories", {})
    meta     = report.get("meta", {})
    per_job  = report.get("per_job", [])

    total_inst   = summary.get("total_instances", 0)
    total_jobs   = summary.get("total_jobs_impacted", 0)
    effort_hrs   = summary.get("total_effort_hours", 0)
    severity     = summary.get("severity", "LOW")

    # ── Severity colour ──────────────────────────────────────────────────
    sev_map = {
        "CRITICAL": ("#be123c", "#fff1f2", "#fda4af", "🔴"),
        "HIGH":     ("#b45309", "#fffbeb", "#fcd34d", "🟠"),
        "MEDIUM":   ("#0369a1", "#eff6ff", "#bfdbfe", "🟡"),
        "LOW":      ("#15803d", "#f0fdf4", "#86efac", "🟢"),
    }
    sev_fg, sev_bg, sev_bd, sev_icon = sev_map.get(severity, sev_map["LOW"])

    if total_inst == 0:
        st.success("✅ No unsupported components detected. Repository is cloud-migration ready.")
        return

    # ── Top summary bar ──────────────────────────────────────────────────
    st.markdown(
        f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;'
        f'border-left:4px solid {sev_fg};padding:14px 18px;margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;">'
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.08em;color:#64748b;">Unsupported Components Report</div>'
        f'<span style="display:inline-block;padding:3px 12px;border-radius:20px;'
        f'background:{sev_bg};border:1px solid {sev_bd};color:{sev_fg};'
        f'font-size:12px;font-weight:700;">{sev_icon} {severity} Impact</span>'
        f'</div>'
        f'<div style="display:flex;gap:24px;margin-top:10px;flex-wrap:wrap;">'
        f'<div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:700;">Total Instances</div>'
        f'<div style="font-size:22px;font-weight:800;color:#0f172a;">{total_inst}</div></div>'
        f'<div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:700;">Jobs Impacted</div>'
        f'<div style="font-size:22px;font-weight:800;color:#0f172a;">{total_jobs}</div></div>'
        f'<div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;font-weight:700;">Est. Effort</div>'
        f'<div style="font-size:22px;font-weight:800;color:{sev_fg};">{effort_hrs}h</div></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ── Category cards ───────────────────────────────────────────────────
    cat_order = ["tJava*", "tSystem", "Custom JDBC", "Custom Routines"]
    active_cats = [k for k in cat_order if cats.get(k, {}).get("count", 0) > 0]

    if active_cats:
        cols = st.columns(len(active_cats))
        for col, key in zip(cols, active_cats):
            m    = meta.get(key, {})
            c    = cats.get(key, {})
            fg   = m.get("color", "#64748b")
            sev  = m.get("severity", "—")
            sev_badge_colors = {
                "CRITICAL": ("#fff1f2", "#fda4af", "#be123c"),
                "HIGH":     ("#fffbeb", "#fcd34d", "#b45309"),
                "MEDIUM":   ("#eff6ff", "#bfdbfe", "#0369a1"),
                "LOW":      ("#f0fdf4", "#86efac", "#15803d"),
            }
            s_bg, s_bd, s_fg = sev_badge_colors.get(sev, ("#f1f5f9", "#cbd5e1", "#64748b"))
            with col:
                st.markdown(
                    f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;'
                    f'border-top:3px solid {fg};padding:14px 14px 10px;">'
                    f'<div style="font-size:10px;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:.06em;color:#64748b;">{m.get("icon","")} {key}</div>'
                    f'<div style="font-size:28px;font-weight:800;color:{fg};margin-top:4px;">'
                    f'{c.get("count", 0)}</div>'
                    f'<div style="font-size:11px;color:#475569;margin-top:2px;">'
                    f'{c.get("job_count", 0)} job{"s" if c.get("job_count",0) != 1 else ""} · '
                    f'{c.get("effort_hours", 0)}h effort</div>'
                    f'<div style="margin-top:6px;">'
                    f'<span style="background:{s_bg};color:{s_fg};border:1px solid {s_bd};'
                    f'border-radius:4px;padding:1px 7px;font-size:10px;font-weight:700;">'
                    f'{sev}</span></div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Per-category expandable detail ───────────────────────────────────
    for key in cat_order:
        c = cats.get(key, {})
        if not c.get("count", 0):
            continue
        m        = meta.get(key, {})
        fg       = m.get("color", "#64748b")
        icon     = m.get("icon", "")
        instances = c.get("instances", [])
        jobs_list = c.get("jobs", [])

        with st.expander(
            f"{icon} **{key}** — {c['count']} instance{'s' if c['count'] != 1 else ''} "
            f"across {c.get('job_count', 0)} job{'s' if c.get('job_count', 0) != 1 else ''}",
            expanded=False,
        ):
            # Description + recommendation
            st.markdown(
                f'<div style="background:#f8fafc;border-left:3px solid {fg};'
                f'border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;">'
                f'<div style="font-size:12px;color:#334155;margin-bottom:4px;">'
                f'{m.get("description","")}</div>'
                f'<div style="font-size:11px;color:{fg};font-weight:600;">'
                f'💡 {m.get("recommendation","")}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Instance table
            if key == "Custom Routines":
                rows = []
                for inst in instances:
                    rows.append({
                        "Routine": inst.get("routine", "—"),
                        "Risk":    inst.get("risk", "—"),
                        "Jobs Using": inst.get("count", 0),
                        "Issues": ", ".join(inst.get("risks", [])) or "None detected",
                    })
                if rows:
                    import pandas as pd
                    styled_dataframe(pd.DataFrame(rows), "unsupported_custom_routines", use_container_width=True, hide_index=True)
            else:
                rows = []
                for inst in instances:
                    breakdown = inst.get("breakdown", {})
                    bd_str = ", ".join(f"{ct}Ã—{n}" for ct, n in breakdown.items()) if breakdown else key
                    rows.append({
                        "Job":        inst.get("job", "—"),
                        "Count":      inst.get("count", 0),
                        "Components": bd_str,
                    })
                if rows:
                    import pandas as pd
                    styled_dataframe(pd.DataFrame(rows), "unsupported_component_instances", use_container_width=True, hide_index=True)

            # Impacted jobs list
            if jobs_list:
                st.caption(f"📍 Impacted jobs: {', '.join(jobs_list[:20])}"
                           + (f" +{len(jobs_list)-20} more" if len(jobs_list) > 20 else ""))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_") or "data"


def risk_badge(value: str) -> str:
    """Return a colored HTML risk badge."""
    level = str(value or "UNKNOWN").upper()
    colors = {
        "CRITICAL": ("#fff1f2", "#fda4af", "#e53e3e"),
        "HIGH": ("#fff1f2", "#fda4af", "#e53e3e"),
        "MEDIUM": ("#fefce8", "#fde68a", "#d69e2e"),
        "LOW": ("#f0fdf4", "#86efac", "#38a169"),
        "READY": ("#f0fdf4", "#86efac", "#38a169"),
        "NOT READY": ("#fff1f2", "#fda4af", "#e53e3e"),
        "UNKNOWN": ("#f8fafc", "#cbd5e1", "#475569"),
    }
    bg, bd, fg = colors.get(level, colors["UNKNOWN"])
    safe_level = html.escape(level)
    return (
        f'<span class="tma-risk-badge" style="background:{bg};border:1px solid {bd};'
        f'color:{fg};border-radius:999px;padding:2px 8px;font-size:11px;'
        f'font-weight:800;white-space:nowrap;">{safe_level}</span>'
    )


def empty_state_card(title: str, body: str = "", status: str = "info", icon: str = "", button_label: str = "", button_key: str = "") -> bool:
    """Styled empty-state card for pages with no current data.

    If `button_label` is provided, renders an action button below the card and
    returns True when it was clicked (False otherwise).
    """
    colors = {
        "info": ("#1d4ed8", "#eff6ff", "#bfdbfe"),
        "success": ("#15803d", "#f0fdf4", "#86efac"),
        "warning": ("#b45309", "#fffbeb", "#fcd34d"),
        "error": ("#be123c", "#fff1f2", "#fda4af"),
    }.get(status, ("#1d4ed8", "#eff6ff", "#bfdbfe"))
    fg, bg, bd = colors
    body_html = f'<div style="font-size:12px;color:#475569;margin-top:4px;">{html.escape(body)}</div>' if body else ""
    icon_html = f'<div style="font-size:28px;margin-bottom:6px;">{html.escape(icon)}</div>' if icon else ""
    st.markdown(
        f'<div class="tma-empty-state" style="background:{bg};border:1px solid {bd};'
        f'border-radius:8px;padding:20px 18px;margin:8px 0;text-align:center;">'
        f'{icon_html}'
        f'<div style="font-size:14px;font-weight:800;color:{fg};">{html.escape(title)}</div>'
        f'{body_html}</div>',
        unsafe_allow_html=True,
    )
    if button_label:
        c1, c2, c3 = st.columns([2, 1, 2])
        with c2:
            return st.button(button_label, key=button_key or f"empty_state_{_slug(title)}", use_container_width=True)
    return False


def render_clickable_kpi_row(items: list[dict], state_key: str, key_prefix: str) -> str | None:
    """Render up to 12 KPI cards (large value, small label, colour accent,
    height<=100px) as a single row; clicking a card toggles a drilldown
    filter stored in session_state[state_key]."""
    visible_items = items[:12]
    if not visible_items:
        return st.session_state.get(state_key)

    st.markdown(
        """
        <style>
        .tma-kpi-card{
            position:relative;background:#fff;border:1px solid #dbe3ef;
            border-radius:8px;border-top:3px solid var(--kc,#1d4ed8);
            padding:8px 10px 6px;height:92px;max-height:100px;box-sizing:border-box;
            box-shadow:0 1px 2px rgba(15,23,42,.05);
            display:flex;flex-direction:column;justify-content:center;
            overflow:hidden;
        }
        .tma-kpi-card.tma-kpi-active{box-shadow:0 0 0 2px var(--kc,#1d4ed8) inset}
        .tma-kpi-label{
            font-size:9.5px;font-weight:800;color:#64748b;
            text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px;
        }
        .tma-kpi-value{
            font-size:24px;font-weight:900;line-height:1;color:var(--kc,#1d4ed8);
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
        }
        .tma-kpi-caption{
            font-size:10px;color:#94a3b8;margin-top:3px;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    current = st.session_state.get(state_key)
    cols = st.columns(len(visible_items))
    for col, item in zip(cols, visible_items):
        label = item.get("label", "")
        value = item.get("value", "-")
        caption = item.get("caption", "")
        color = item.get("color", "#1d4ed8")
        filter_value = item.get("filter", label)
        active = " tma-kpi-active" if current == filter_value else ""
        btn_key = f"{key_prefix}_{_slug(label)}"
        with col:
            st.markdown(
                f'<div class="tma-kpi-card{active}" style="--kc:{html.escape(str(color))}">'
                f'<div class="tma-kpi-label">{html.escape(str(label))}</div>'
                f'<div class="tma-kpi-value">{html.escape(str(value))}</div>'
                f'<div class="tma-kpi-caption">{html.escape(str(caption))}</div>'
                f'</div>'
                f'<style>'
                f'div.st-key-{btn_key} {{margin-top:-96px!important;height:92px!important;}}'
                f'div.st-key-{btn_key} button {{'
                f'  height:92px!important;width:100%!important;'
                f'  opacity:0;cursor:pointer;padding:0!important;border:none!important;'
                f'  background:transparent!important;'
                f'}}'
                f'</style>',
                unsafe_allow_html=True,
            )
            if st.button(" ", key=btn_key, use_container_width=True):
                new_value = None if current == filter_value else filter_value
                st.session_state[state_key] = new_value
                st.session_state["kpi_filter"] = new_value
                st.rerun()

    selected = st.session_state.get(state_key)
    if selected:
        c1, c2 = st.columns([5, 1])
        with c1:
            st.caption(f"Drilldown filter: {selected}")
        with c2:
            if st.button("Clear", key=f"{key_prefix}_clear", use_container_width=True):
                st.session_state[state_key] = None
                st.session_state["kpi_filter"] = None
                st.rerun()
    st.session_state["kpi_filter"] = st.session_state.get(state_key)
    return st.session_state.get(state_key)


def styled_dataframe(df, key: str, csv_label: str = "Download CSV", **kwargs) -> None:
    """Render a dataframe with a CSV export control, zebra striping and rounded corners."""
    if df is None or getattr(df, "empty", False):
        empty_state_card("No rows to display", "This table will populate after analysis data is available.")
        return
    st.markdown(
        """
        <style>
        [data-testid="stDataFrame"], [data-testid="stDataFrameResizable"] {
            border-radius: var(--tma-radius, 10px) !important;
            overflow: hidden !important;
            border: 1px solid var(--tma-border, #e2e8f0) !important;
        }
        [data-testid="stDataFrame"] [role="row"]:nth-of-type(even),
        [data-testid="stDataFrameResizable"] [role="row"]:nth-of-type(even) {
            background-color: #f8fafc !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Use a per-run counter in session_state to guarantee unique widget keys
    # even when the same logical key is rendered multiple times in one script run.
    counter_key = "_styled_df_counter"
    st.session_state[counter_key] = st.session_state.get(counter_key, 0) + 1
    unique_key = f"csv_{_slug(key)}_{st.session_state[counter_key]}"
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        csv_label,
        data=csv,
        file_name=f"{_slug(key)}.csv",
        mime="text/csv",
        key=unique_key,
    )
    st.dataframe(df, **kwargs)


def build_pdf_bytes(title: str, sections: list[tuple[str, object]]) -> bytes | None:
    """Create a compact PDF report using reportlab (already a pinned dependency)."""
    try:
        import io

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except Exception:
        return None

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    elements = [Paragraph(html.escape(title), styles["Title"]), Spacer(1, 12)]

    for section_title, data in sections:
        elements.append(Paragraph(html.escape(str(section_title)), styles["Heading2"]))
        elements.append(Spacer(1, 6))
        if hasattr(data, "to_dict"):
            if data is None or getattr(data, "empty", True):
                elements.append(Paragraph("No data available.", styles["Normal"]))
            else:
                table_data = [list(map(str, data.columns))] + data.astype(str).values.tolist()
                table = Table(table_data, repeatRows=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                elements.append(table)
        else:
            elements.append(Paragraph(html.escape(str(data)), styles["Normal"]))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    return buf.getvalue()


def pdf_download_button(title: str, sections: list[tuple[str, object]], key: str, file_name: str) -> None:
    pdf_bytes = build_pdf_bytes(title, sections)
    if pdf_bytes:
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            key=f"pdf_{_slug(key)}",
        )
    else:
        st.button("Download PDF", disabled=True, key=f"pdf_disabled_{_slug(key)}")
        st.caption("Install `reportlab` to enable PDF export.")
