"""
TMA Export Asset Framework
==========================

Centralised asset-collection layer for the Documentation Export Center.

Responsibilities:

1.  Render Plotly figures → PNG bytes (kaleido).
2.  Render Matplotlib figures → PNG bytes.
3.  Render NetworkX graphs → PNG (Matplotlib spring-layout).
4.  Render Mermaid flowcharts → PNG (Mermaid → Graphviz DOT → `dot` binary).
5.  Scan `output/` for any image / chart / diagram artefacts already on disk.
6.  Build per-document asset manifests so every export format (PDF / DOCX /
    HTML / ZIP) embeds *the same* visuals that the user sees in the UI.

Public API:

    AssetManifest       — collection of named PNG/SVG bytes + metadata.
    collect_for_doc(doc_type) -> AssetManifest
    embed_in_markdown(md, manifest) -> str   # rewrites image refs
    plotly_to_png(fig) / matplotlib_to_png(fig) / networkx_to_png(graph)
    mermaid_to_png(mermaid_code) / dot_to_png(dot_source)
    scan_disk_assets(root="output") -> list[Asset]

The module degrades gracefully — missing libraries (kaleido / matplotlib /
graphviz) only disable the corresponding renderer, never break exports.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Asset:
    """A single visual asset embedded into an export."""
    key: str                     # unique slug, also used as file name
    kind: str                    # "image" | "chart" | "diagram" | "lineage"
    mime: str                    # image/png · image/svg+xml · image/jpeg
    data: bytes                  # raw bytes
    caption: str = ""            # human-readable caption
    source: str = ""             # provenance: "plotly", "matplotlib",
                                 # "networkx", "mermaid", "disk"

    @property
    def filename(self) -> str:
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/svg+xml": "svg",
            "image/gif": "gif",
        }.get(self.mime, "png")
        return f"{self.key}.{ext}"


@dataclass
class AssetManifest:
    """Container for all assets belonging to one exported document."""
    doc_type: str
    assets: List[Asset] = field(default_factory=list)

    def add(self, asset: Asset) -> None:
        self.assets.append(asset)

    def by_kind(self, kind: str) -> List[Asset]:
        return [a for a in self.assets if a.kind == kind]

    @property
    def total_bytes(self) -> int:
        return sum(len(a.data) for a in self.assets)

    @property
    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for a in self.assets:
            out[a.kind] = out.get(a.kind, 0) + 1
        return out


# ── Renderers (all isolated, all defensive) ──────────────────────────────────

def plotly_to_png(fig, width: int = 900, height: int = 500) -> Optional[bytes]:
    """Render a Plotly figure to PNG bytes via kaleido. Returns None on failure."""
    try:
        import kaleido  # noqa: F401
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception:
        return None


def matplotlib_to_png(fig, dpi: int = 150) -> Optional[bytes]:
    """Render a Matplotlib figure to PNG bytes. Returns None on failure."""
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        buf.seek(0)
        return buf.read()
    except Exception:
        return None


def networkx_to_png(graph, layout: str = "spring", figsize: Tuple[int, int] = (10, 6),
                    node_color: str = "#1d4ed8", edge_color: str = "#94a3b8") -> Optional[bytes]:
    """Render a NetworkX graph to PNG via Matplotlib (no GUI dependency)."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt
        import networkx as nx

        fig, ax = plt.subplots(figsize=figsize)
        if layout == "shell":
            pos = nx.shell_layout(graph)
        elif layout == "circular":
            pos = nx.circular_layout(graph)
        elif layout == "kamada":
            pos = nx.kamada_kawai_layout(graph)
        else:
            pos = nx.spring_layout(graph, k=0.6, seed=42)
        nx.draw_networkx_nodes(graph, pos, ax=ax, node_color=node_color, node_size=600, alpha=0.9)
        nx.draw_networkx_edges(graph, pos, ax=ax, edge_color=edge_color, arrows=True, arrowsize=12, width=1.2)
        nx.draw_networkx_labels(graph, pos, ax=ax, font_size=8, font_color="#ffffff")
        edge_labels = nx.get_edge_attributes(graph, "label")
        if edge_labels:
            nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, ax=ax, font_size=7)
        ax.set_axis_off()
        return matplotlib_to_png(fig)
    except Exception:
        return None


def dot_to_png(dot_source: str) -> Optional[bytes]:
    """Render a Graphviz DOT string to PNG bytes via the `dot` binary."""
    try:
        if not shutil.which("dot"):
            return None
        proc = subprocess.run(
            ["dot", "-Tpng"],
            input=dot_source.encode("utf-8"),
            capture_output=True, timeout=20,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
    except Exception:
        return None
    return None


def mermaid_to_png(mermaid_code: str) -> Optional[bytes]:
    """Convert a Mermaid flowchart to PNG by routing through Graphviz DOT.

    Uses the project's existing `mermaid_to_dot` converter so the output looks
    visually consistent with what `st.graphviz_chart()` already renders inside
    the UI.
    """
    try:
        from app.ui.design_system_v2 import mermaid_to_dot
        dot = mermaid_to_dot(mermaid_code)
        if not dot:
            return None
        return dot_to_png(dot)
    except Exception:
        return None


# ── Disk scanner ─────────────────────────────────────────────────────────────

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".svg")
_DIAGRAM_HINTS = ("diagram", "flow", "lineage", "architecture", "graph", "wave")
_CHART_HINTS = ("chart", "kpi", "metric", "score", "complexity")


def _classify(filename: str) -> str:
    lo = filename.lower()
    if any(h in lo for h in _DIAGRAM_HINTS):
        return "diagram"
    if any(h in lo for h in _CHART_HINTS):
        return "chart"
    return "image"


def _safe_slug(text: str) -> str:
    out = "".join(c if c.isalnum() else "_" for c in str(text)).strip("_")
    return out or "asset"


def scan_disk_assets(root: str = "output", limit: int = 64) -> List[Asset]:
    """Pick up image / SVG / chart files already produced by other parts of TMA."""
    out: List[Asset] = []
    if not os.path.isdir(root):
        return out
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not f.lower().endswith(_IMAGE_EXTS):
                continue
            path = os.path.join(dirpath, f)
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
            except Exception:
                continue
            ext = f.lower().rsplit(".", 1)[-1]
            mime = {
                "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "gif": "image/gif", "svg": "image/svg+xml",
            }.get(ext, "image/png")
            kind = _classify(f)
            out.append(Asset(
                key=_safe_slug(f.rsplit(".", 1)[0]),
                kind=kind, mime=mime, data=data,
                caption=f, source="disk",
            ))
            if len(out) >= limit:
                return out
    return out


# ── KPI / dashboard chart synthesis (Matplotlib) ─────────────────────────────

def _ensure_mpl():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _palette() -> Dict[str, str]:
    return {
        "GREEN": "#15803d", "AMBER": "#b45309", "RED": "#be123c",
        "LOW": "#15803d", "MEDIUM": "#b45309", "HIGH": "#be123c", "CRITICAL": "#7f1d1d",
        "primary": "#1d4ed8", "secondary": "#0f766e", "accent": "#6d28d9",
    }


def chart_kpis(values: Dict[str, Any], title: str = "Executive KPIs") -> Optional[Asset]:
    """Horizontal bar chart of KPI values."""
    try:
        plt = _ensure_mpl()
        # Coerce non-numeric KPIs to strings displayed as labels
        numeric, label = [], []
        for k, v in values.items():
            try:
                numeric.append(float(str(v).rstrip("%").strip()))
                label.append(k)
            except Exception:
                continue
        if not numeric:
            return None
        fig, ax = plt.subplots(figsize=(8, max(3, len(label) * 0.45)))
        bars = ax.barh(label, numeric, color=_palette()["primary"])
        ax.invert_yaxis()
        ax.set_title(title, fontsize=13, fontweight="bold", color="#1a3c6e")
        for b, v in zip(bars, numeric):
            ax.text(b.get_width(), b.get_y() + b.get_height() / 2,
                    f" {v:g}", va="center", fontsize=9, color="#0f172a")
        ax.spines[["right", "top"]].set_visible(False)
        ax.tick_params(labelsize=9)
        png = matplotlib_to_png(fig)
        plt.close(fig)
        if not png:
            return None
        return Asset(key=_safe_slug(title), kind="chart", mime="image/png",
                     data=png, caption=title, source="matplotlib")
    except Exception:
        return None


def chart_complexity(by_complexity: Dict[str, int], title: str = "Complexity Distribution") -> Optional[Asset]:
    try:
        plt = _ensure_mpl()
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        labels = [k for k in order if k in by_complexity]
        if not labels:
            labels = list(by_complexity.keys())
        values = [by_complexity.get(k, 0) for k in labels]
        if not any(values):
            return None
        colors = [_palette().get(k, "#64748b") for k in labels]
        fig, ax = plt.subplots(figsize=(7, 4.5))
        wedges, _texts, autotexts = ax.pie(
            values, labels=labels, colors=colors, autopct="%1.0f%%",
            textprops={"color": "#0f172a", "fontsize": 10}, startangle=90,
        )
        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontweight("bold")
        ax.set_title(title, fontsize=13, fontweight="bold", color="#1a3c6e")
        png = matplotlib_to_png(fig)
        plt.close(fig)
        if not png:
            return None
        return Asset(key=_safe_slug(title), kind="chart", mime="image/png",
                     data=png, caption=title, source="matplotlib")
    except Exception:
        return None


def chart_readiness(jobs: List[Dict[str, Any]], title: str = "Readiness RAG") -> Optional[Asset]:
    """Stacked-bar of READY / WARNING / FAILED counts."""
    try:
        plt = _ensure_mpl()
        from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag

        def _rag(j):
            cr = j.get("cloud_readiness", {}) or {}
            if "readiness" in cr:
                return {"HIGH": "GREEN", "MEDIUM": "AMBER", "LOW": "RED"}.get(cr.get("readiness"), "AMBER")
            if "score" in cr:
                return _score_to_rag(cr.get("score", 0))
            return cr.get("rag", "AMBER")

        cnt = {"GREEN": 0, "AMBER": 0, "RED": 0}
        for j in jobs:
            cnt[_rag(j)] = cnt.get(_rag(j), 0) + 1
        fig, ax = plt.subplots(figsize=(6.5, 3.5))
        labels = ["Ready", "Warning", "Failed"]
        vals = [cnt["GREEN"], cnt["AMBER"], cnt["RED"]]
        cols = [_palette()["GREEN"], _palette()["AMBER"], _palette()["RED"]]
        ax.bar(labels, vals, color=cols)
        for i, v in enumerate(vals):
            ax.text(i, v, str(v), ha="center", va="bottom", fontsize=10, fontweight="bold")
        ax.set_title(title, fontsize=13, fontweight="bold", color="#1a3c6e")
        ax.spines[["right", "top"]].set_visible(False)
        png = matplotlib_to_png(fig)
        plt.close(fig)
        if not png:
            return None
        return Asset(key=_safe_slug(title), kind="chart", mime="image/png",
                     data=png, caption=title, source="matplotlib")
    except Exception:
        return None


def diagram_lineage(jobs: List[Dict[str, Any]], title: str = "Repository Data Lineage") -> Optional[Asset]:
    """Build a simple NetworkX graph from job → component flow and render it."""
    try:
        import networkx as nx
        G = nx.DiGraph()
        for j in jobs[:20]:  # cap for readability
            jname = j.get("job_data", {}).get("job_name", "Job")
            G.add_node(jname)
            for c in (j.get("job_data", {}).get("components") or [])[:6]:
                cname = c.get("name") or c.get("component_name") or c.get("type") or "comp"
                node = f"{jname}/{cname}"
                G.add_node(node)
                G.add_edge(jname, node)
        if not G.nodes:
            return None
        png = networkx_to_png(G)
        if not png:
            return None
        return Asset(key=_safe_slug(title), kind="lineage", mime="image/png",
                     data=png, caption=title, source="networkx")
    except Exception:
        return None


def diagram_architecture(jobs: List[Dict[str, Any]], title: str = "Architecture Overview") -> Optional[Asset]:
    """Architecture-style Graphviz diagram from job set."""
    try:
        if not jobs:
            return None
        nodes = []
        # Sources
        for j in jobs[:10]:
            jname = j.get("job_data", {}).get("job_name", "Job")
            nodes.append(jname)
        dot_lines = [
            'digraph G {',
            '  rankdir=LR;',
            '  bgcolor="#ffffff";',
            '  node [shape=box, style="rounded,filled", fillcolor="#dbeafe", color="#1d4ed8", fontname="Helvetica"];',
            '  Source [label="Source\\nSystems", fillcolor="#fef3c7", color="#b45309"];',
            '  Talend [label="Talend Jobs", fillcolor="#e9d5ff", color="#6d28d9"];',
            '  Target [label="Target\\nPlatform", fillcolor="#bbf7d0", color="#15803d"];',
            '  Source -> Talend -> Target;',
        ]
        for n in nodes:
            safe = _safe_slug(n)
            dot_lines.append(f'  {safe} [label="{n}"];')
            dot_lines.append(f'  Talend -> {safe};')
        dot_lines.append("}")
        dot = "\n".join(dot_lines)
        png = dot_to_png(dot)
        if not png:
            return None
        return Asset(key=_safe_slug(title), kind="diagram", mime="image/png",
                     data=png, caption=title, source="graphviz")
    except Exception:
        return None


def diagram_mermaid(mermaid_code: str, key: str, caption: str) -> Optional[Asset]:
    png = mermaid_to_png(mermaid_code)
    if not png:
        return None
    return Asset(key=_safe_slug(key), kind="diagram", mime="image/png",
                 data=png, caption=caption, source="mermaid")


# ── Per-document asset collection ────────────────────────────────────────────

def _session_state():
    try:
        import streamlit as st
        return st.session_state
    except Exception:
        return {}


def collect_for_doc(doc_type: str) -> AssetManifest:
    """Build a manifest of every visual that should appear in the export."""
    ss = _session_state()
    jobs = ss.get("last_analysis_jobs", []) or []
    manifest = AssetManifest(doc_type=doc_type)

    # Always pick up disk-side images / pre-rendered charts.
    for a in scan_disk_assets("output"):
        manifest.add(a)

    if not jobs:
        return manifest

    effort = ss.get("effort_estimate") or {}
    by_complexity = effort.get("by_complexity") or {}

    if doc_type in ("Executive Report",):
        kpi = {
            "Total Jobs": len(jobs),
            "Automation %": effort.get("auto_pct", 0),
            "Estimated Days": effort.get("estimated_days", 0),
            "Estimated Weeks": effort.get("estimated_weeks", 0) or 0,
        }
        a = chart_kpis(kpi, "Executive KPIs")
        if a:
            manifest.add(a)
        if by_complexity:
            a = chart_complexity(by_complexity, "Complexity Distribution")
            if a:
                manifest.add(a)
        a = chart_readiness(jobs, "Readiness RAG")
        if a:
            manifest.add(a)

    if doc_type in ("TDD", "LLD"):
        if by_complexity:
            a = chart_complexity(by_complexity, "Complexity Distribution")
            if a:
                manifest.add(a)
        a = diagram_lineage(jobs, "Data Lineage")
        if a:
            manifest.add(a)

    if doc_type in ("Architecture Report",):
        a = diagram_architecture(jobs, "Architecture Overview")
        if a:
            manifest.add(a)
        a = diagram_lineage(jobs, "System Integration Map")
        if a:
            manifest.add(a)

    if doc_type in ("Migration Runbook",):
        a = chart_readiness(jobs, "Pre-Migration Readiness")
        if a:
            manifest.add(a)

    if doc_type in ("Migration Report",):
        a = chart_kpis(
            {"Total Jobs": len(jobs),
             "Automation %": effort.get("auto_pct", 0),
             "Manual %": effort.get("manual_pct", 0)},
            "Migration Intelligence KPIs",
        )
        if a:
            manifest.add(a)
        if by_complexity:
            a = chart_complexity(by_complexity, "Wave Planning Complexity")
            if a:
                manifest.add(a)

    if doc_type in ("Validation Report",):
        a = chart_readiness(jobs, "Validation Coverage Snapshot")
        if a:
            manifest.add(a)

    # Render any flowcharts from FlowchartGenerator (Mermaid) for TDD / LLD / Arch.
    if doc_type in ("TDD", "LLD", "Architecture Report"):
        try:
            from app.tiap.graph.flowchart_generator import FlowchartGenerator
            flows = FlowchartGenerator().generate(jobs)
            for k, label in [("technical_flow", "Technical Flow"),
                             ("business_flow", "Business Flow"),
                             ("repository_flow", "Repository Flow")]:
                code = flows.get(k)
                if not code:
                    continue
                a = diagram_mermaid(str(code), f"{doc_type}_{k}", label)
                if a:
                    manifest.add(a)
        except Exception:
            pass

    return manifest


# ── Markdown helpers (image embedding) ───────────────────────────────────────

# Convention used for export-friendly image markdown:
#   ![caption](asset:key)
# `key` is the Asset.key. Each format-specific writer translates this
# placeholder to its native equivalent (HTML <img>, reportlab Image flowable,
# python-docx add_picture).
_IMG_RE = re.compile(r'!\[(?P<caption>[^\]]*)\]\(asset:(?P<key>[A-Za-z0-9_\-]+)\)')


def asset_image_md(key: str, caption: str = "") -> str:
    """Markdown placeholder rendered later by format-specific writers."""
    return f"![{caption}](asset:{key})"


def parse_asset_refs(markdown: str) -> List[Tuple[str, str]]:
    return [(m.group("key"), m.group("caption")) for m in _IMG_RE.finditer(markdown or "")]


def replace_assets_html(markdown: str, manifest: AssetManifest, base_url: str = "Assets") -> str:
    """Convert `asset:` placeholders to `<img>` tags using a relative folder."""
    by_key = {a.key: a for a in manifest.assets}

    def _repl(m: re.Match) -> str:
        key = m.group("key")
        caption = m.group("caption")
        a = by_key.get(key)
        if not a:
            return ""
        return f'<figure><img src="{base_url}/{a.filename}" alt="{caption}"/><figcaption>{caption}</figcaption></figure>'

    return _IMG_RE.sub(_repl, markdown or "")


def replace_assets_inline_b64(markdown: str, manifest: AssetManifest) -> str:
    """Inline base64 alternative — used for single-file HTML exports."""
    import base64
    by_key = {a.key: a for a in manifest.assets}

    def _repl(m: re.Match) -> str:
        key = m.group("key")
        caption = m.group("caption")
        a = by_key.get(key)
        if not a:
            return ""
        b64 = base64.b64encode(a.data).decode("ascii")
        return f'<figure><img src="data:{a.mime};base64,{b64}" alt="{caption}"/><figcaption>{caption}</figcaption></figure>'

    return _IMG_RE.sub(_repl, markdown or "")
