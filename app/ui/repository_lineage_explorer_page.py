"""
Repository Lineage Explorer
============================
Cross-job lineage: Source System → Job A → Job B → Job C → Target System
Click-through node detail: Metadata / Expressions / Dependencies / Impact
"""

from __future__ import annotations

import html as _html
from collections import defaultdict
from typing import Optional

import pandas as pd
import streamlit as st

from app.lineage.repository_lineage_index import build_repository_index, RepositoryLineageIndex
from app.lineage.lineage_model import NodeType, LineageNode
from app.lineage.lineage_traversal import trace_forward
from app.ui.design_system_v2 import render_mermaid_diagram

# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
.rle-header{font-size:22px;font-weight:800;color:#1a1a18;margin-bottom:4px;}
.rle-sub{font-size:13px;color:#8a8a85;margin-bottom:20px;}
.rle-section{font-size:11px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:#8a8a85;margin:18px 0 8px;}
.rle-kpi{background:#fff;border:1px solid #e4e3dc;border-left:4px solid #3C3489;
  border-radius:10px;padding:12px 16px;}
.rle-kpi-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;
  letter-spacing:.07em;margin-bottom:5px;}
.rle-kpi-val{font-size:26px;font-weight:800;color:#3C3489;line-height:1;}
.rle-kpi-sub{font-size:11px;color:#8a8a85;margin-top:3px;}
.rle-chain{background:#f7f6f1;border:1px solid #e4e3dc;border-radius:10px;
  padding:14px 18px;margin-bottom:10px;}
.rle-chain-title{font-size:13px;font-weight:700;color:#3C3489;margin-bottom:8px;}
.rle-chain-step{display:flex;align-items:center;gap:8px;padding:3px 0;
  font-size:12px;color:#2d2d2a;}
.rle-chain-arrow{color:#8a8a85;font-size:16px;margin-left:18px;}
.rle-badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;
  border-radius:20px;margin:0 2px;}
.rle-empty{font-size:13px;color:#9e9e96;font-style:italic;padding:10px 0;}
.rle-node-src{background:#e3f2fd;color:#1565c0;border-radius:6px;
  padding:3px 10px;font-weight:700;}
.rle-node-job{background:#f3e5f5;color:#6a1b9a;border-radius:6px;
  padding:3px 10px;font-weight:700;}
.rle-node-tgt{background:#e8f5e9;color:#2e7d32;border-radius:6px;
  padding:3px 10px;font-weight:700;}
/* Node detail panel */
.rnd-panel{background:#fff;border:1px solid #e4e3dc;border-radius:12px;
  padding:18px 20px;margin-bottom:14px;}
.rnd-panel-title{font-size:15px;font-weight:800;color:#3C3489;margin-bottom:4px;}
.rnd-panel-sub{font-size:12px;color:#8a8a85;margin-bottom:12px;}
.rnd-meta-row{display:flex;gap:8px;margin-bottom:6px;align-items:flex-start;}
.rnd-meta-key{font-size:11px;font-weight:700;color:#8a8a85;min-width:110px;
  text-transform:uppercase;letter-spacing:.05em;padding-top:2px;}
.rnd-meta-val{font-size:12px;color:#1a1a18;flex:1;}
.rnd-expr-box{background:#f7f6f1;border-left:3px solid #3C3489;border-radius:4px;
  padding:8px 12px;font-family:monospace;font-size:11px;color:#2d2d2a;
  margin-bottom:6px;word-break:break-all;}
.rnd-dep-item{background:#f0ede6;border-radius:6px;padding:6px 12px;
  margin-bottom:4px;font-size:12px;color:#3a3a36;}
.rnd-impact-item{background:#fef8ee;border-left:3px solid #e65100;
  border-radius:4px;padding:6px 12px;margin-bottom:4px;font-size:12px;}
.rnd-select-hint{background:#e8eaf6;border-radius:8px;padding:12px 16px;
  font-size:13px;color:#3949ab;margin-bottom:12px;}
/* Search */
.rls-hit{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;
  padding:10px 14px;margin-bottom:6px;cursor:pointer;}
.rls-hit-title{font-size:13px;font-weight:700;color:#1a1a18;}
.rls-hit-meta{font-size:11px;color:#8a8a85;margin-top:2px;}
.rls-hit-type{display:inline-block;font-size:10px;font-weight:700;padding:1px 8px;
  border-radius:12px;margin-right:6px;}
.rls-path-step{display:inline-flex;align-items:center;font-size:12px;}
.rls-path-arrow{color:#8a8a85;margin:0 4px;}
.rls-highlight{background:#fffde7;border:2px solid #f9a825;border-radius:6px;padding:2px 6px;}
.rls-no-results{font-size:13px;color:#9e9e96;font-style:italic;padding:16px 0;}
.rls-search-bar{background:#f7f6f1;border-radius:10px;padding:14px 18px;margin-bottom:14px;}
</style>
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kpi(label: str, value, sub: str, color: str = "#3C3489") -> str:
    return (
        f'<div class="rle-kpi" style="border-left-color:{color};">'
        f'<div class="rle-kpi-label">{label}</div>'
        f'<div class="rle-kpi-val" style="color:{color};">{value}</div>'
        f'<div class="rle-kpi-sub">{sub}</div></div>'
    )


def _section(text: str) -> None:
    st.markdown(f'<div class="rle-section">{text}</div>', unsafe_allow_html=True)


def _divider() -> None:
    st.markdown(
        "<hr style='border:none;border-top:1px solid #e4e3dc;margin:18px 0;'>",
        unsafe_allow_html=True,
    )


def _empty(msg: str) -> None:
    st.markdown(
        f'<div class="rle-empty">{_html.escape(msg)}</div>',
        unsafe_allow_html=True,
    )


def _safe_id(name: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name))


def _meta_row(key: str, val: str) -> str:
    if not val:
        return ""
    return (
        f'<div class="rnd-meta-row">'
        f'<div class="rnd-meta-key">{_html.escape(key)}</div>'
        f'<div class="rnd-meta-val">{_html.escape(str(val))}</div>'
        f'</div>'
    )


# ── Load / cache index ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _build_index(job_keys: tuple) -> RepositoryLineageIndex:
    jobs = st.session_state.get("last_analysis_jobs", [])
    return build_repository_index(jobs)


def _get_index() -> Optional[RepositoryLineageIndex]:
    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        return None
    key = tuple(sorted(
        (j.get("job_data", {}).get("job_name") or j.get("job_name", ""), j.get("file_path", ""))
        for j in jobs
    ))
    return _build_index(key)


# ── Graph helpers ─────────────────────────────────────────────────────────────

def _build_chain_graph(index: RepositoryLineageIndex) -> dict:
    downstream: dict[str, set[str]] = defaultdict(set)
    upstream:   dict[str, set[str]] = defaultdict(set)
    for edge in index.bridge_edges:
        sn = index.graph.get_node(edge.source_node_id)
        tn = index.graph.get_node(edge.target_node_id)
        if sn and tn and sn.job_name and tn.job_name:
            downstream[sn.job_name].add(tn.job_name)
            upstream[tn.job_name].add(sn.job_name)
    all_jobs = set(downstream.keys()) | set(upstream.keys()) | set(index.job_graphs.keys())
    return {"downstream": dict(downstream), "upstream": dict(upstream), "all_jobs": all_jobs}


def _topo_sort(downstream: dict, all_jobs: set) -> list:
    in_degree = {j: 0 for j in all_jobs}
    for src, dsts in downstream.items():
        for d in dsts:
            in_degree[d] = in_degree.get(d, 0) + 1
    queue = sorted(j for j, deg in in_degree.items() if deg == 0)
    result = []
    while queue:
        node = queue.pop(0)
        result.append(node)
        for nxt in sorted(downstream.get(node, [])):
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)
    for j in sorted(all_jobs):
        if j not in result:
            result.append(j)
    return result


def _src_tables(index: RepositoryLineageIndex, job_name: str) -> list:
    g = index.job_graphs.get(job_name)
    if not g:
        return []
    return sorted({
        n.table or n.metadata.get("table", "")
        for n in g.nodes
        if n.node_type == NodeType.SOURCE_TABLE and (n.table or n.metadata.get("table", ""))
    })


def _tgt_tables(index: RepositoryLineageIndex, job_name: str) -> list:
    g = index.job_graphs.get(job_name)
    if not g:
        return []
    return sorted({
        n.table or n.metadata.get("table", "")
        for n in g.nodes
        if n.node_type == NodeType.TARGET_TABLE and (n.table or n.metadata.get("table", ""))
    })


def _bridge_tables(index: RepositoryLineageIndex, from_job: str, to_job: str) -> list:
    tbls = []
    for edge in index.bridge_edges:
        sn = index.graph.get_node(edge.source_node_id)
        tn = index.graph.get_node(edge.target_node_id)
        if sn and tn and sn.job_name == from_job and tn.job_name == to_job:
            t = sn.table or sn.metadata.get("table", "")
            if t:
                tbls.append(t)
    return sorted(set(tbls))


# ── Node catalogue: all clickable nodes ──────────────────────────────────────

def _all_nodes_catalogue(index: RepositoryLineageIndex) -> dict[str, LineageNode]:
    """Return display_label → node for every node in the combined graph."""
    catalogue: dict[str, LineageNode] = {}
    for node in index.graph.nodes:
        t = node.table or node.metadata.get("table", "")
        lbl_parts = []
        if node.job_name:
            lbl_parts.append(node.job_name)
        if t:
            lbl_parts.append(t)
        if node.component_name:
            lbl_parts.append(f"[{node.component_name}]")
        lbl = " / ".join(lbl_parts) if lbl_parts else (node.label or node.id)
        # Make unique
        base = lbl
        i = 2
        while lbl in catalogue:
            lbl = f"{base} #{i}"
            i += 1
        catalogue[lbl] = node
    return catalogue


# ══════════════════════════════════════════════════════════════════════════════
# NODE DETAIL PANEL (click-through)
# ══════════════════════════════════════════════════════════════════════════════

def _render_node_detail(node: LineageNode, index: RepositoryLineageIndex) -> None:
    """Render the 4-section detail panel for a selected node."""

    type_icon = {
        NodeType.SOURCE_TABLE:  "📥",
        NodeType.TARGET_TABLE:  "📤",
        NodeType.COMPONENT:     "⚙️",
        NodeType.LOOKUP_TABLE:  "🔵",
    }.get(node.node_type, "🔷")

    type_label = node.node_type.value.replace("_", " ").title()

    st.markdown(
        f'<div class="rnd-panel">'
        f'<div class="rnd-panel-title">{type_icon} {_html.escape(node.label or node.id)}</div>'
        f'<div class="rnd-panel-sub">{type_label} · Job: {_html.escape(node.job_name or "—")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    det_tab1, det_tab2, det_tab3, det_tab4 = st.tabs([
        "📋 Metadata", "🧮 Expressions", "🔗 Dependencies", "💥 Impact"
    ])

    # ── Tab 1: Metadata ───────────────────────────────────────────────────────
    with det_tab1:
        rows_html = ""
        rows_html += _meta_row("Node ID",        node.id)
        rows_html += _meta_row("Type",           type_label)
        rows_html += _meta_row("Job",            node.job_name)
        rows_html += _meta_row("Label",          node.label)
        rows_html += _meta_row("System Type",    node.system_type)
        rows_html += _meta_row("Database",       node.database)
        rows_html += _meta_row("Schema",         node.schema)
        rows_html += _meta_row("Table",          node.table or node.metadata.get("table", ""))
        rows_html += _meta_row("Component Name", node.component_name)
        rows_html += _meta_row("Component Type", node.component_type)
        rows_html += _meta_row("Physical Key",   node.physical_identity)

        # Extra metadata dict keys
        skip = {"table", "system_type", "database", "schema", "component_name", "component_type"}
        for k, v in node.metadata.items():
            if k not in skip and v:
                rows_html += _meta_row(k.replace("_", " ").title(), str(v))

        if rows_html:
            st.markdown(f'<div class="rnd-panel">{rows_html}</div>', unsafe_allow_html=True)
        else:
            _empty("No metadata available.")

        # Incoming / outgoing edge summary
        in_edges  = index.graph.edges_to(node.id)
        out_edges = index.graph.edges_from(node.id)
        c1, c2 = st.columns(2)
        c1.metric("Incoming Edges", len(in_edges))
        c2.metric("Outgoing Edges", len(out_edges))

    # ── Tab 2: Expressions ────────────────────────────────────────────────────
    with det_tab2:
        all_edges = index.graph.edges_from(node.id) + index.graph.edges_to(node.id)
        expr_edges = [e for e in all_edges if e.expression]

        if not expr_edges:
            _empty("No expressions found for this node.")
        else:
            for e in expr_edges:
                sn = index.graph.get_node(e.source_node_id)
                tn = index.graph.get_node(e.target_node_id)
                src_lbl = (sn.label or sn.id) if sn else e.source_node_id
                tgt_lbl = (tn.label or tn.id) if tn else e.target_node_id
                st.markdown(
                    f'<div style="font-size:11px;color:#8a8a85;margin-bottom:2px;">'
                    f'{_html.escape(src_lbl)} → {_html.escape(tgt_lbl)}'
                    f'<span style="margin-left:8px;background:#e8eaf6;padding:1px 6px;'
                    f'border-radius:4px;color:#3949ab;">{_html.escape(e.rule or e.rule_type)}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="rnd-expr-box">{_html.escape(e.expression)}</div>',
                    unsafe_allow_html=True,
                )

        # Also show column-level expressions from metadata
        col_exprs = node.metadata.get("expressions", [])
        if col_exprs:
            _section("Column-level expressions")
            for ex in col_exprs:
                st.markdown(f'<div class="rnd-expr-box">{_html.escape(str(ex))}</div>',
                            unsafe_allow_html=True)

    # ── Tab 3: Dependencies ───────────────────────────────────────────────────
    with det_tab3:
        in_edges  = index.graph.edges_to(node.id)
        out_edges = index.graph.edges_from(node.id)

        _section(f"⬆ Upstream nodes ({len(in_edges)})")
        if in_edges:
            dep_rows = []
            for e in in_edges:
                sn = index.graph.get_node(e.source_node_id)
                if sn:
                    dep_rows.append({
                        "Node":   sn.label or sn.id,
                        "Type":   sn.node_type.value,
                        "Job":    sn.job_name or "—",
                        "Table":  sn.table or sn.metadata.get("table", "—"),
                        "Rule":   e.rule or e.rule_type or "—",
                    })
            if dep_rows:
                st.dataframe(pd.DataFrame(dep_rows), use_container_width=True, hide_index=True)
        else:
            _empty("No upstream dependencies (this is a root node).")

        _divider()

        _section(f"⬇ Downstream nodes ({len(out_edges)})")
        if out_edges:
            dep_rows = []
            for e in out_edges:
                tn = index.graph.get_node(e.target_node_id)
                if tn:
                    dep_rows.append({
                        "Node":  tn.label or tn.id,
                        "Type":  tn.node_type.value,
                        "Job":   tn.job_name or "—",
                        "Table": tn.table or tn.metadata.get("table", "—"),
                        "Rule":  e.rule or e.rule_type or "—",
                    })
            if dep_rows:
                st.dataframe(pd.DataFrame(dep_rows), use_container_width=True, hide_index=True)
        else:
            _empty("No downstream dependencies (this is a terminal node).")

        # Cross-job bridge deps
        bridge_in  = [e for e in index.bridge_edges if e.target_node_id == node.id]
        bridge_out = [e for e in index.bridge_edges if e.source_node_id == node.id]
        if bridge_in or bridge_out:
            _divider()
            _section("🌉 Cross-job bridge connections")
            for e in bridge_in + bridge_out:
                sn = index.graph.get_node(e.source_node_id)
                tn = index.graph.get_node(e.target_node_id)
                direction = "← from" if e.target_node_id == node.id else "→ to"
                other = sn if e.target_node_id == node.id else tn
                if other:
                    st.markdown(
                        f'<div class="rnd-dep-item">'
                        f'{direction} <strong>{_html.escape(other.job_name or "?")}</strong>'
                        f' via <code>{_html.escape(other.table or other.id)}</code>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

    # ── Tab 4: Impact ─────────────────────────────────────────────────────────
    with det_tab4:
        st.caption("All downstream nodes reachable from this node (forward traversal).")

        fwd = trace_forward(index.graph, node.id, max_hops=15)

        affected_nodes  = [
            index.graph.get_node(nid)
            for nid in fwd.visited_nodes
            if nid != node.id
        ]
        affected_nodes  = [n for n in affected_nodes if n]

        affected_tables = sorted({
            n.table or n.metadata.get("table", "")
            for n in affected_nodes
            if n.node_type in (NodeType.TARGET_TABLE, NodeType.SOURCE_TABLE)
            and (n.table or n.metadata.get("table", ""))
        })
        affected_jobs   = sorted({
            n.job_name for n in affected_nodes if n.job_name and n.job_name != node.job_name
        })

        k1, k2, k3 = st.columns(3)
        k1.metric("Downstream Nodes",  len(affected_nodes))
        k2.metric("Downstream Tables", len(affected_tables))
        k3.metric("Downstream Jobs",   len(affected_jobs))

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        if affected_tables:
            _section("📤 Downstream tables")
            st.dataframe(
                pd.DataFrame({"Table": affected_tables}),
                use_container_width=True, hide_index=True,
            )

        if affected_jobs:
            _section("⚙️ Downstream jobs")
            st.dataframe(
                pd.DataFrame({"Job": affected_jobs}),
                use_container_width=True, hide_index=True,
            )

        if affected_nodes:
            _section("🔢 All affected nodes")
            rows = []
            for n in affected_nodes:
                rows.append({
                    "Node":   n.label or n.id,
                    "Type":   n.node_type.value,
                    "Job":    n.job_name or "—",
                    "Table":  n.table or n.metadata.get("table", "—"),
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                         height=min(400, 40 + 35 * len(rows)))

        if fwd.has_cycles:
            st.warning(f"⚠️ {len(fwd.cycles_detected)} cycle(s) detected during impact traversal.")

        if not affected_nodes:
            _empty("No downstream impact detected — this is a terminal node.")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW: Repository Overview
# ══════════════════════════════════════════════════════════════════════════════

def _render_overview(index: RepositoryLineageIndex) -> None:
    chain_data  = _build_chain_graph(index)
    downstream  = chain_data["downstream"]
    upstream    = chain_data["upstream"]
    all_jobs    = chain_data["all_jobs"]

    # KPI strip
    cols = st.columns(4)
    for col, (lbl, val, sub, color) in zip(cols, [
        ("Total Jobs",      index.stats.total_jobs,     "in repository",     "#3C3489"),
        ("Unique Tables",   index.stats.unique_tables,  "across all jobs",   "#0369a1"),
        ("Cross-Job Links", index.stats.cross_job_links,"shared table refs", "#7c3aed"),
        ("Bridge Edges",    len(index.bridge_edges),    "cross-job flows",   "#e65100"),
    ]):
        col.markdown(_kpi(lbl, val, sub, color), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    _divider()

    topo = _topo_sort(downstream, all_jobs)

    # Identify external sources/targets
    written: set[str] = set()
    for jn in all_jobs:
        for t in _tgt_tables(index, jn):
            written.add(t.lower())

    read_tbls:  dict[str, list[str]] = {jn: _src_tables(index, jn) for jn in all_jobs}
    write_tbls: dict[str, list[str]] = {jn: _tgt_tables(index, jn) for jn in all_jobs}

    ext_sources: set[str] = set()
    for jn in all_jobs:
        for t in read_tbls.get(jn, []):
            if t.lower() not in written:
                ext_sources.add(t)

    leaf_jobs = {j for j in all_jobs if not downstream.get(j)}
    ext_targets: set[str] = set()
    for jn in leaf_jobs:
        for t in write_tbls.get(jn, []):
            ext_targets.add(t)

    _section("📊 Cross-job lineage flow")

    lines = ["graph TD"]
    for src in sorted(ext_sources):
        nid = f"ESRC_{_safe_id(src)}"
        lines.append(f'    {nid}[("📥 {src}")]')
        lines.append(f'    style {nid} fill:#e3f2fd,stroke:#1565c0,color:#1565c0')

    for jn in topo:
        nid = f"JOB_{_safe_id(jn)}"
        sc = len(read_tbls.get(jn, []))
        tc = len(write_tbls.get(jn, []))
        label = f"⚙️ {jn}\\n{sc} in → {tc} out"
        lines.append(f'    {nid}["{label}"]')
        lines.append(f'    style {nid} fill:#f3e5f5,stroke:#6a1b9a,color:#4a1a7a')

    for tgt in sorted(ext_targets):
        nid = f"ETGT_{_safe_id(tgt)}"
        lines.append(f'    {nid}[("📤 {tgt}")]')
        lines.append(f'    style {nid} fill:#e8f5e9,stroke:#2e7d32,color:#2e7d32')

    for jn in all_jobs:
        for t in read_tbls.get(jn, []):
            if t in ext_sources:
                lines.append(f'    ESRC_{_safe_id(t)} -->|"reads"| JOB_{_safe_id(jn)}')

    seen_bridge: set[tuple] = set()
    for fj, to_jobs in downstream.items():
        for tj in sorted(to_jobs):
            bt = _bridge_tables(index, fj, tj)
            lbl = bt[0] if bt else "shared table"
            key = (fj, tj)
            if key not in seen_bridge:
                seen_bridge.add(key)
                lines.append(f'    JOB_{_safe_id(fj)} -->|"{lbl}"| JOB_{_safe_id(tj)}')

    for jn in leaf_jobs:
        for t in write_tbls.get(jn, []):
            if t in ext_targets:
                lines.append(f'    JOB_{_safe_id(jn)} -->|"writes"| ETGT_{_safe_id(t)}')

    if len(lines) > 1:
        h = max(400, 120 * len(topo) + 80 * (len(ext_sources) + len(ext_targets)))
        render_mermaid_diagram("\n".join(lines), height=min(h, 900))

    st.markdown(
        '<div class="rnd-select-hint">👇 Select a node below to explore its Metadata, '
        'Expressions, Dependencies, and Impact.</div>',
        unsafe_allow_html=True,
    )

    _divider()

    # ── CLICK-THROUGH: node selector ─────────────────────────────────────────
    _section("🖱️ Node click-through explorer")

    catalogue = _all_nodes_catalogue(index)
    node_labels = ["— select a node —"] + sorted(catalogue.keys())

    # Allow pre-selection via session state (e.g. from job detail view)
    default_idx = 0
    presel = st.session_state.get("_rle_selected_node_id")
    if presel:
        for i, lbl in enumerate(node_labels):
            if lbl in catalogue and catalogue[lbl].id == presel:
                default_idx = i
                break

    sel_label = st.selectbox(
        "Select node to inspect",
        node_labels,
        index=default_idx,
        key="_rle_node_sel_overview",
    )

    if sel_label and sel_label != "— select a node —":
        node = catalogue[sel_label]
        st.session_state["_rle_selected_node_id"] = node.id
        _divider()
        _render_node_detail(node, index)

    _divider()

    # Cross-job dependency table
    _section("📋 Cross-job dependency table")
    rows = []
    for jn in topo:
        up  = sorted(upstream.get(jn, []))
        dwn = sorted(downstream.get(jn, []))
        rows.append({
            "Job":             jn,
            "Upstream Jobs":   ", ".join(up)  or "— (source)",
            "Downstream Jobs": ", ".join(dwn) or "— (terminal)",
            "Source Tables":   len(read_tbls.get(jn, [])),
            "Target Tables":   len(write_tbls.get(jn, [])),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW: Job Detail
# ══════════════════════════════════════════════════════════════════════════════

def _render_job_detail(index: RepositoryLineageIndex) -> None:
    chain_data = _build_chain_graph(index)
    all_jobs   = sorted(chain_data["all_jobs"])
    downstream = chain_data["downstream"]
    upstream   = chain_data["upstream"]

    if not all_jobs:
        _empty("No jobs found.")
        return

    sel_job = st.selectbox("Select Job", all_jobs, key="_rle_job_detail_sel")

    up_jobs  = sorted(upstream.get(sel_job, []))
    dwn_jobs = sorted(downstream.get(sel_job, []))
    src_tbls = _src_tables(index, sel_job)
    tgt_tbls = _tgt_tables(index, sel_job)

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(_kpi("Upstream Jobs",   len(up_jobs),  "feed this job",      "#0369a1"), unsafe_allow_html=True)
    k2.markdown(_kpi("Downstream Jobs", len(dwn_jobs), "this job feeds",     "#7c3aed"), unsafe_allow_html=True)
    k3.markdown(_kpi("Source Tables",   len(src_tbls), "read by this job",   "#0891b2"), unsafe_allow_html=True)
    k4.markdown(_kpi("Target Tables",   len(tgt_tbls), "written by this job","#2e7d32"), unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _divider()

    _section("🔄 Job lineage subgraph")

    lines = ["graph LR"]
    this_id = f"THIS_{_safe_id(sel_job)}"
    lines.append(f'    {this_id}["⚙️ {sel_job}"]')
    lines.append(f'    style {this_id} fill:#f3e5f5,stroke:#6a1b9a,color:#4a1a7a,font-weight:bold')

    for uj in up_jobs:
        nid = f"UP_{_safe_id(uj)}"
        lines.append(f'    {nid}["⚙️ {uj}"]')
        bridge = _bridge_tables(index, uj, sel_job)
        lbl = bridge[0] if bridge else "→"
        lines.append(f'    {nid} -->|"{lbl}"| {this_id}')

    for dj in dwn_jobs:
        nid = f"DWN_{_safe_id(dj)}"
        lines.append(f'    {nid}["⚙️ {dj}"]')
        bridge = _bridge_tables(index, sel_job, dj)
        lbl = bridge[0] if bridge else "→"
        lines.append(f'    {this_id} -->|"{lbl}"| {nid}')

    written: set[str] = set()
    for jn in chain_data["all_jobs"]:
        for t in _tgt_tables(index, jn):
            written.add(t.lower())
    for t in src_tbls:
        if t.lower() not in written:
            nid = f"ESRC_{_safe_id(t)}"
            lines.append(f'    {nid}[("📥 {t}")]')
            lines.append(f'    style {nid} fill:#e3f2fd,stroke:#1565c0,color:#1565c0')
            lines.append(f'    {nid} --> {this_id}')

    if not dwn_jobs:
        for t in tgt_tbls[:5]:
            nid = f"ETGT_{_safe_id(t)}"
            lines.append(f'    {nid}[("📤 {t}")]')
            lines.append(f'    style {nid} fill:#e8f5e9,stroke:#2e7d32,color:#2e7d32')
            lines.append(f'    {this_id} --> {nid}')

    render_mermaid_diagram("\n".join(lines),
                           height=max(300, 100 + 80 * (len(up_jobs) + len(dwn_jobs) + 2)))

    _divider()

    # ── Node selector for this job ────────────────────────────────────────────
    _section("🖱️ Node click-through explorer")
    st.markdown(
        '<div class="rnd-select-hint">Select any node from this job to inspect its '
        'Metadata, Expressions, Dependencies, and Impact.</div>',
        unsafe_allow_html=True,
    )

    job_graph = index.job_graphs.get(sel_job)
    if job_graph:
        job_nodes: dict[str, LineageNode] = {}
        for node in job_graph.nodes:
            t = node.table or node.metadata.get("table", "")
            parts = []
            if node.node_type.value:
                parts.append(node.node_type.value)
            if t:
                parts.append(t)
            if node.component_name:
                parts.append(f"[{node.component_name}]")
            lbl = " / ".join(parts) if parts else (node.label or node.id)
            base = lbl
            i = 2
            while lbl in job_nodes:
                lbl = f"{base} #{i}"
                i += 1
            job_nodes[lbl] = node

        job_node_labels = ["— select a node —"] + sorted(job_nodes.keys())
        sel_node_lbl = st.selectbox(
            "Select node",
            job_node_labels,
            key=f"_rle_node_sel_job_{sel_job}",
        )
        if sel_node_lbl and sel_node_lbl != "— select a node —":
            _divider()
            _render_node_detail(job_nodes[sel_node_lbl], index)
    else:
        _empty("No graph data for this job.")

    _divider()

    c1, c2 = st.columns(2)
    with c1:
        _section("📥 Source Tables")
        if src_tbls:
            st.dataframe(pd.DataFrame({"Table": src_tbls}),
                         use_container_width=True, hide_index=True)
        else:
            _empty("None detected.")
    with c2:
        _section("📤 Target Tables")
        if tgt_tbls:
            st.dataframe(pd.DataFrame({"Table": tgt_tbls}),
                         use_container_width=True, hide_index=True)
        else:
            _empty("None detected.")

    _divider()

    _section("🔗 Bridge Tables (shared with other jobs)")
    bridge_rows = []
    for edge in index.bridge_edges:
        sn = index.graph.get_node(edge.source_node_id)
        tn = index.graph.get_node(edge.target_node_id)
        if sn and tn and (sn.job_name == sel_job or tn.job_name == sel_job):
            t = sn.table or sn.metadata.get("table", "")
            direction = "→ feeds" if sn.job_name == sel_job else "← fed by"
            other_job = tn.job_name if sn.job_name == sel_job else sn.job_name
            bridge_rows.append({"Direction": direction, "Shared Table": t, "Other Job": other_job})
    if bridge_rows:
        st.dataframe(pd.DataFrame(bridge_rows), use_container_width=True, hide_index=True)
    else:
        _empty("No cross-job bridge connections.")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW: Table Lineage
# ══════════════════════════════════════════════════════════════════════════════

def _render_table_lineage(index: RepositoryLineageIndex) -> None:
    all_tables = sorted(index.all_tables())
    if not all_tables:
        _empty("No tables found across repository.")
        return

    sel_table = st.selectbox("Select Table", all_tables, key="_rle_table_sel")

    chain_data = _build_chain_graph(index)
    reader_jobs, writer_jobs = [], []
    for jn in chain_data["all_jobs"]:
        if sel_table.upper() in [t.upper() for t in _src_tables(index, jn)]:
            reader_jobs.append(jn)
        if sel_table.upper() in [t.upper() for t in _tgt_tables(index, jn)]:
            writer_jobs.append(jn)

    k1, k2 = st.columns(2)
    k1.markdown(_kpi("Jobs That Write", len(writer_jobs), "produce this table", "#e65100"), unsafe_allow_html=True)
    k2.markdown(_kpi("Jobs That Read",  len(reader_jobs), "consume this table", "#0369a1"), unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _divider()

    _section("🔄 Table flow diagram")
    lines = ["graph LR"]
    tbl_id = f"TBL_{_safe_id(sel_table)}"
    lines.append(f'    {tbl_id}[("🗄️ {sel_table}")]')
    lines.append(f'    style {tbl_id} fill:#fff3e0,stroke:#e65100,color:#bf360c,font-weight:bold')
    for wj in writer_jobs:
        nid = f"WJ_{_safe_id(wj)}"
        lines.append(f'    {nid}["⚙️ {wj}"]')
        lines.append(f'    style {nid} fill:#f3e5f5,stroke:#6a1b9a,color:#4a1a7a')
        lines.append(f'    {nid} -->|"writes"| {tbl_id}')
    for rj in reader_jobs:
        nid = f"RJ_{_safe_id(rj)}"
        lines.append(f'    {nid}["⚙️ {rj}"]')
        lines.append(f'    style {nid} fill:#f3e5f5,stroke:#6a1b9a,color:#4a1a7a')
        lines.append(f'    {tbl_id} -->|"reads"| {nid}')
    render_mermaid_diagram("\n".join(lines),
                           height=max(250, 100 + 70 * (len(writer_jobs) + len(reader_jobs))))

    _divider()

    # ── Node selector for this table ──────────────────────────────────────────
    _section("🖱️ Node click-through explorer")
    st.markdown(
        '<div class="rnd-select-hint">Select a node related to this table to inspect '
        'its Metadata, Expressions, Dependencies, and Impact.</div>',
        unsafe_allow_html=True,
    )

    # Collect all nodes referencing this table
    table_nodes: dict[str, LineageNode] = {}
    for node in index.graph.nodes:
        t = node.table or node.metadata.get("table", "")
        if t.upper() == sel_table.upper():
            parts = [node.node_type.value]
            if node.job_name:
                parts.append(node.job_name)
            if node.component_name:
                parts.append(f"[{node.component_name}]")
            lbl = " / ".join(parts) if parts else (node.label or node.id)
            base = lbl
            i = 2
            while lbl in table_nodes:
                lbl = f"{base} #{i}"
                i += 1
            table_nodes[lbl] = node

    if table_nodes:
        tn_labels = ["— select a node —"] + sorted(table_nodes.keys())
        sel_tn = st.selectbox("Select node", tn_labels, key=f"_rle_node_sel_tbl_{sel_table}")
        if sel_tn and sel_tn != "— select a node —":
            _divider()
            _render_node_detail(table_nodes[sel_tn], index)
    else:
        _empty("No nodes found for this table in the graph.")

    _divider()

    c1, c2 = st.columns(2)
    with c1:
        _section("✏️ Written by")
        if writer_jobs:
            st.dataframe(pd.DataFrame({"Job": writer_jobs}),
                         use_container_width=True, hide_index=True)
        else:
            _empty("No job writes this table (external source).")
    with c2:
        _section("📖 Read by")
        if reader_jobs:
            st.dataframe(pd.DataFrame({"Job": reader_jobs}),
                         use_container_width=True, hide_index=True)
        else:
            _empty("No job reads this table (terminal target).")


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _search_nodes(
    index: RepositoryLineageIndex,
    query: str,
    search_type: str,  # "table" | "column" | "job" | "all"
) -> list[LineageNode]:
    """Return nodes matching query, filtered by search_type."""
    q = query.strip().lower()
    if not q:
        return []

    results: list[LineageNode] = []
    seen: set[str] = set()

    for node in index.graph.nodes:
        if node.id in seen:
            continue

        t      = (node.table or node.metadata.get("table", "")).lower()
        jn     = (node.job_name or "").lower()
        cname  = (node.component_name or "").lower()
        lbl    = (node.label or "").lower()
        # column info lives on edges - collect from outgoing edge column names
        cols   = set()
        for e in index.graph.edges_from(node.id):
            if e.source_column:
                cols.add(e.source_column.lower())
            if e.target_column:
                cols.add(e.target_column.lower())
        for e in index.graph.edges_to(node.id):
            if e.source_column:
                cols.add(e.source_column.lower())
            if e.target_column:
                cols.add(e.target_column.lower())

        matched = False
        if search_type in ("table", "all"):
            if q in t or q in lbl:
                matched = True
        if search_type in ("column", "all"):
            if any(q in c for c in cols):
                matched = True
        if search_type in ("job", "all"):
            if q in jn or q in cname:
                matched = True

        if matched:
            results.append(node)
            seen.add(node.id)

    return results


def _build_highlight_path_diagram(
    index: RepositoryLineageIndex,
    hit_node_ids: set[str],
    chain_data: dict,
) -> str:
    """Build a graphviz-compatible Mermaid diagram with matched nodes highlighted."""
    downstream = chain_data["downstream"]
    upstream   = chain_data["upstream"]
    all_jobs   = chain_data["all_jobs"]
    topo       = _topo_sort(downstream, all_jobs)

    # Collect job-level highlight: jobs that contain a hit node
    hit_jobs: set[str] = set()
    for nid in hit_node_ids:
        node = index.graph.get_node(nid)
        if node and node.job_name:
            hit_jobs.add(node.job_name)

    # Trace forward+backward from each hit job to find the lineage path
    path_jobs: set[str] = set(hit_jobs)
    for hj in list(hit_jobs):
        # walk upstream
        cur = hj
        visited_up: set[str] = set()
        q = [cur]
        while q:
            j = q.pop(0)
            if j in visited_up:
                continue
            visited_up.add(j)
            path_jobs.add(j)
            for uj in upstream.get(j, []):
                q.append(uj)
        # walk downstream
        cur = hj
        visited_dn: set[str] = set()
        q = [cur]
        while q:
            j = q.pop(0)
            if j in visited_dn:
                continue
            visited_dn.add(j)
            path_jobs.add(j)
            for dj in downstream.get(j, []):
                q.append(dj)

    written: set[str] = set()
    for jn in all_jobs:
        for t in _tgt_tables(index, jn):
            written.add(t.lower())

    read_tbls  = {jn: _src_tables(index, jn) for jn in all_jobs}
    write_tbls = {jn: _tgt_tables(index, jn) for jn in all_jobs}

    ext_sources: set[str] = set()
    for jn in all_jobs:
        for t in read_tbls.get(jn, []):
            if t.lower() not in written:
                ext_sources.add(t)

    leaf_jobs = {j for j in all_jobs if not downstream.get(j)}
    ext_targets: set[str] = set()
    for jn in leaf_jobs:
        for t in write_tbls.get(jn, []):
            ext_targets.add(t)

    lines = ["graph TD"]

    for src in sorted(ext_sources):
        nid = f"ESRC_{_safe_id(src)}"
        lines.append(f'    {nid}[("📥 {src}")]')
        # highlight if a hit node touches this table
        hit_this = any(
            (index.graph.get_node(hn) and
             (index.graph.get_node(hn).table or "").upper() == src.upper())
            for hn in hit_node_ids
        )
        fill = "#fffde7" if hit_this else "#e3f2fd"
        stroke = "#f9a825" if hit_this else "#1565c0"
        sw = "3px" if hit_this else "1px"
        lines.append(f'    style {nid} fill:{fill},stroke:{stroke},stroke-width:{sw},color:#1565c0')

    for jn in topo:
        nid = f"JOB_{_safe_id(jn)}"
        sc = len(read_tbls.get(jn, []))
        tc = len(write_tbls.get(jn, []))
        star = " ★" if jn in hit_jobs else ""
        label = f"⚙️ {jn}{star}\\n{sc} in → {tc} out"
        lines.append(f'    {nid}["{label}"]')
        is_hit    = jn in hit_jobs
        is_path   = jn in path_jobs
        is_dimmed = jn not in path_jobs and bool(hit_node_ids)
        if is_hit:
            lines.append(f'    style {nid} fill:#fffde7,stroke:#f9a825,stroke-width:3px,color:#4a1a7a,font-weight:bold')
        elif is_path:
            lines.append(f'    style {nid} fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px,color:#4a1a7a')
        elif is_dimmed:
            lines.append(f'    style {nid} fill:#f5f5f5,stroke:#ccc,color:#aaa')
        else:
            lines.append(f'    style {nid} fill:#f3e5f5,stroke:#6a1b9a,color:#4a1a7a')

    for tgt in sorted(ext_targets):
        nid = f"ETGT_{_safe_id(tgt)}"
        lines.append(f'    {nid}[("📤 {tgt}")]')
        hit_this = any(
            (index.graph.get_node(hn) and
             (index.graph.get_node(hn).table or "").upper() == tgt.upper())
            for hn in hit_node_ids
        )
        fill = "#fffde7" if hit_this else "#e8f5e9"
        stroke = "#f9a825" if hit_this else "#2e7d32"
        sw = "3px" if hit_this else "1px"
        lines.append(f'    style {nid} fill:{fill},stroke:{stroke},stroke-width:{sw},color:#2e7d32')

    for jn in all_jobs:
        for t in read_tbls.get(jn, []):
            if t in ext_sources:
                lines.append(f'    ESRC_{_safe_id(t)} -->|"reads"| JOB_{_safe_id(jn)}')

    seen_bridge: set[tuple] = set()
    for fj, to_jobs in downstream.items():
        for tj in sorted(to_jobs):
            key = (fj, tj)
            if key not in seen_bridge:
                seen_bridge.add(key)
                bt = _bridge_tables(index, fj, tj)
                lbl = bt[0] if bt else "→"
                # highlight edge if both jobs are on the path
                lines.append(f'    JOB_{_safe_id(fj)} -->|"{lbl}"| JOB_{_safe_id(tj)}')

    for jn in leaf_jobs:
        for t in write_tbls.get(jn, []):
            if t in ext_targets:
                lines.append(f'    JOB_{_safe_id(jn)} -->|"writes"| ETGT_{_safe_id(t)}')

    return "\n".join(lines)


def _node_type_badge(node: LineageNode) -> str:
    colors = {
        NodeType.SOURCE_TABLE:  ("#e3f2fd", "#1565c0"),
        NodeType.TARGET_TABLE:  ("#e8f5e9", "#2e7d32"),
        NodeType.COMPONENT:     ("#f3e5f5", "#6a1b9a"),
        NodeType.LOOKUP_TABLE:  ("#fff3e0", "#e65100"),
    }
    bg, fg = colors.get(node.node_type, ("#f5f5f5", "#424242"))
    lbl = node.node_type.value.replace("_", " ")
    return (
        f'<span class="rls-hit-type" style="background:{bg};color:{fg};">'
        f'{lbl}</span>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# VIEW: Lineage Search
# ══════════════════════════════════════════════════════════════════════════════

def _render_lineage_search(index: RepositoryLineageIndex) -> None:
    """Search by table / column / job — highlight matching lineage path."""

    chain_data = _build_chain_graph(index)

    st.markdown('<div class="rls-search-bar">', unsafe_allow_html=True)
    sc1, sc2 = st.columns([3, 1])
    with sc1:
        query = st.text_input(
            "🔍 Search lineage",
            placeholder="e.g. CUSTOMERS, order_id, Load_Orders…",
            key="_rls_query",
            label_visibility="collapsed",
        )
    with sc2:
        search_type = st.selectbox(
            "Search type",
            ["all", "table", "column", "job"],
            format_func=lambda x: {"all": "All", "table": "Table", "column": "Column", "job": "Job"}[x],
            key="_rls_type",
            label_visibility="collapsed",
        )
    st.markdown('</div>', unsafe_allow_html=True)

    if not query or len(query.strip()) < 2:
        st.markdown(
            '<div class="rls-no-results">Enter at least 2 characters to search tables, '
            'columns, or jobs across the entire repository lineage graph.</div>',
            unsafe_allow_html=True,
        )
        return

    hits = _search_nodes(index, query, search_type)

    if not hits:
        st.markdown(
            f'<div class="rls-no-results">No matches found for <strong>{_html.escape(query)}</strong> '
            f'in {search_type} scope.</div>',
            unsafe_allow_html=True,
        )
        return

    hit_node_ids = {n.id for n in hits}

    # ── Result count ─────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="font-size:13px;color:#3C3489;font-weight:700;margin-bottom:10px;">'
        f'✅ {len(hits)} match{"es" if len(hits) != 1 else ""} for '
        f'<span class="rls-highlight">{_html.escape(query)}</span></div>',
        unsafe_allow_html=True,
    )

    # ── Highlighted lineage diagram ───────────────────────────────────────────
    _section("🗺️ Highlighted lineage path (★ = matched nodes)")
    st.caption("Yellow nodes = matches. Purple border = lineage path. Grey = unrelated.")
    diagram = _build_highlight_path_diagram(index, hit_node_ids, chain_data)
    all_jobs = chain_data["all_jobs"]
    h = max(400, 100 * len(all_jobs))
    render_mermaid_diagram(diagram, height=min(h, 1000))

    _divider()

    # ── Hit list + column-level path ─────────────────────────────────────────
    _section(f"📋 Search results ({len(hits)})")

    # Collect column matches per node for column search
    col_matches: dict[str, list[str]] = {}
    if search_type in ("column", "all"):
        q_lower = query.strip().lower()
        for node in hits:
            matched_cols: list[str] = []
            for e in index.graph.edges_from(node.id) + index.graph.edges_to(node.id):
                for c in [e.source_column, e.target_column]:
                    if c and q_lower in c.lower() and c not in matched_cols:
                        matched_cols.append(c)
            if matched_cols:
                col_matches[node.id] = matched_cols

    for i, node in enumerate(hits[:50]):
        t     = node.table or node.metadata.get("table", "")
        jn    = node.job_name or "—"
        lbl   = node.label or t or node.id
        cols  = col_matches.get(node.id, [])

        # Build lineage path text: upstream jobs → this → downstream jobs
        up_jobs = []
        dn_jobs = []
        if node.job_name:
            # walk graph edges for upstream/downstream job chain
            for be in index.bridge_edges:
                sn = index.graph.get_node(be.source_node_id)
                tn = index.graph.get_node(be.target_node_id)
                if sn and tn:
                    if tn.job_name == node.job_name and sn.job_name not in up_jobs:
                        up_jobs.append(sn.job_name)
                    if sn.job_name == node.job_name and tn.job_name not in dn_jobs:
                        dn_jobs.append(tn.job_name)

        path_parts = []
        for uj in up_jobs[:2]:
            path_parts.append(f'<span class="rls-path-step">⚙️ {_html.escape(uj)}</span>')
        if node.job_name:
            path_parts.append(
                f'<span class="rls-path-step rls-highlight">⚙️ {_html.escape(node.job_name)}</span>'
            )
        for dj in dn_jobs[:2]:
            path_parts.append(f'<span class="rls-path-step">⚙️ {_html.escape(dj)}</span>')

        path_html = '<span class="rls-path-arrow">→</span>'.join(path_parts) if path_parts else ""

        col_html = ""
        if cols:
            col_html = (
                '<div style="margin-top:4px;">'
                + "".join(
                    f'<span class="rle-badge" style="background:#fff3e0;color:#e65100;">'
                    f'col: {_html.escape(c)}</span>'
                    for c in cols[:8]
                )
                + "</div>"
            )

        st.markdown(
            f'<div class="rls-hit">'
            f'<div class="rls-hit-title">'
            f'{_node_type_badge(node)}'
            f'{_html.escape(lbl)}'
            f'</div>'
            f'<div class="rls-hit-meta">'
            f'Job: <strong>{_html.escape(jn)}</strong>'
            + (f' &nbsp;·&nbsp; Table: <strong>{_html.escape(t)}</strong>' if t else "")
            + (f' &nbsp;·&nbsp; System: {_html.escape(node.system_type)}' if node.system_type else "")
            + '</div>'
            + (f'<div style="margin-top:5px;">{path_html}</div>' if path_html else "")
            + col_html
            + '</div>',
            unsafe_allow_html=True,
        )

    if len(hits) > 50:
        st.caption(f"Showing first 50 of {len(hits)} results. Refine your search.")

    _divider()

    # ── Node detail for selected hit ──────────────────────────────────────────
    _section("🖱️ Inspect a result node")
    hit_labels = {
        f"{n.node_type.value} / {n.job_name or '—'} / {n.table or n.metadata.get('table', '') or n.id}": n
        for n in hits
    }
    # deduplicate labels
    deduped: dict[str, LineageNode] = {}
    for lbl, node in hit_labels.items():
        base, i = lbl, 2
        while lbl in deduped:
            lbl = f"{base} #{i}"
            i += 1
        deduped[lbl] = node

    sel_labels = ["— select to inspect —"] + sorted(deduped.keys())
    sel = st.selectbox("Select result node", sel_labels, key="_rls_node_inspect")
    if sel and sel != "— select to inspect —":
        _divider()
        _render_node_detail(deduped[sel], index)


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════════════════════

def _render_repository_dashboard(index: RepositoryLineageIndex) -> None:
    """📊 Repository Dashboard: deep lineage statistics across the whole repository."""
    stats = index.graph.statistics()

    _section("📊 Repository lineage statistics")

    cols = st.columns(4)
    for col, (lbl, val, sub, color) in zip(cols, [
        ("Nodes",            stats["node_count"],          "total lineage nodes",   "#3C3489"),
        ("Edges",            stats["edge_count"],          "total connections",     "#0369a1"),
        ("Jobs Represented", stats["job_count"],            "with lineage nodes",    "#7c3aed"),
        ("Distinct Tables",  stats["distinct_tables"],     "across all jobs",       "#e65100"),
    ]):
        col.markdown(_kpi(lbl, val, sub, color), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    _divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Node types**")
        if stats["node_types"]:
            st.dataframe(
                pd.DataFrame(
                    sorted(stats["node_types"].items(), key=lambda kv: -kv[1]),
                    columns=["Node Type", "Count"],
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            _empty("No nodes in repository graph.")
    with c2:
        st.markdown("**Edge types**")
        if stats["edge_types"]:
            st.dataframe(
                pd.DataFrame(
                    sorted(stats["edge_types"].items(), key=lambda kv: -kv[1]),
                    columns=["Edge Type", "Count"],
                ),
                use_container_width=True, hide_index=True,
            )
        else:
            _empty("No edges in repository graph.")

    _divider()

    c3, c4 = st.columns(2)
    with c3:
        st.markdown(f"**Top fan-out nodes** (avg fan-out: {stats['avg_fan_out']})")
        if stats["top_fan_out"]:
            rows = []
            for nid, cnt in stats["top_fan_out"]:
                n = index.graph.get_node(nid)
                rows.append((n.label if n else nid, cnt))
            st.dataframe(pd.DataFrame(rows, columns=["Node", "Outgoing edges"]),
                         use_container_width=True, hide_index=True)
        else:
            _empty("No fan-out data available.")
    with c4:
        st.markdown("**Top fan-in nodes**")
        if stats["top_fan_in"]:
            rows = []
            for nid, cnt in stats["top_fan_in"]:
                n = index.graph.get_node(nid)
                rows.append((n.label if n else nid, cnt))
            st.dataframe(pd.DataFrame(rows, columns=["Node", "Incoming edges"]),
                         use_container_width=True, hide_index=True)
        else:
            _empty("No fan-in data available.")

    _divider()

    _section(f"🧩 Isolated nodes ({stats['isolated_node_count']})")
    if stats["isolated_node_ids"]:
        rows = []
        for nid in stats["isolated_node_ids"]:
            n = index.graph.get_node(nid)
            rows.append((n.label if n else nid, n.node_type.value if n else "", n.job_name if n else ""))
        st.dataframe(pd.DataFrame(rows, columns=["Node", "Type", "Job"]),
                     use_container_width=True, hide_index=True)
        st.caption("Isolated nodes have no incoming or outgoing edges — often unused tMap outputs or orphaned tables.")
    else:
        _empty("No isolated nodes — every node has at least one connection.")

    _divider()

    _section("🏢 Nodes per job")
    if stats["nodes_per_job"]:
        st.dataframe(
            pd.DataFrame(
                sorted(stats["nodes_per_job"].items(), key=lambda kv: -kv[1]),
                columns=["Job", "Node Count"],
            ),
            use_container_width=True, hide_index=True, height=260,
        )
    else:
        _empty("No per-job node data available.")


def render_repository_lineage_explorer() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

    st.markdown(
        '<div class="rle-header">🗺️ Repository Lineage Explorer</div>'
        '<div class="rle-sub">Cross-job data flow: Source System → Job A → Job B → Job C → Target System. '
        'Click any node to explore Metadata, Expressions, Dependencies, and Impact.</div>',
        unsafe_allow_html=True,
    )

    jobs = st.session_state.get("last_analysis_jobs", [])
    if not jobs:
        return

    with st.spinner("Building repository lineage index…"):
        index = _get_index()

    if index is None:
        st.error("Failed to build lineage index.")
        return

    if index.stats.jobs_parsed == 0:
        st.warning(
            "Repository loaded but no column-mapping data found. "
            "Jobs without tMap components cannot be linked."
        )

    view = st.radio(
        "View",
        ["🔍 Lineage Search", "🗺️ Repository Overview", "⚙️ Job Detail", "🗄️ Table Lineage",
         "📊 Repository Dashboard"],
        horizontal=True,
        key="_rle_view",
    )

    _divider()

    if view == "🔍 Lineage Search":
        _render_lineage_search(index)
    elif view == "🗺️ Repository Overview":
        _render_overview(index)
    elif view == "⚙️ Job Detail":
        _render_job_detail(index)
    elif view == "📊 Repository Dashboard":
        _render_repository_dashboard(index)
    else:
        _render_table_lineage(index)
