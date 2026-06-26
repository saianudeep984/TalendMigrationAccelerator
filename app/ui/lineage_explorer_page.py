"""
Lineage Explorer Tab — Job 360 Analysis
🧭 Primary tab: end-to-end column lineage, impact analysis and data-flow overview.

Views:
  Overview        — KPI strip + job-level data-flow summary diagram
  Column Lineage  — filterable column-level lineage with Mermaid graph
  Impact Analysis — target-column drill-down tracing all upstream fields
"""

from __future__ import annotations

import html as _html
import re
from collections import defaultdict

import pandas as pd
import streamlit as st

from app.ui.column_mapping_service import load_mappings
from app.ui.column_mapping_model import ColumnMapping, MappingRuleDetail
from app.ui.design_system_v2 import render_mermaid_diagram
from app.lineage.lineage_graph_builder import build_graph, _source_node_id
from app.lineage.lineage_traversal import trace_forward, trace_backward
from app.lineage.lineage_model import NodeType, LineageNode, LineageGraph

# ── Constants ─────────────────────────────────────────────────────────────────
LINEAGE_MAX_MAPPINGS = 200

RULE_DISPLAY = {
    "Direct Copy":            ("✅", "Direct Mapping",   "#e8f5e9", "#2e7d32"),
    "Direct Copy (Nullable)": ("✅", "Direct Mapping",   "#e8f5e9", "#2e7d32"),
    "Type Cast":              ("⚙️", "Direct Mapping",   "#fff3e0", "#e65100"),
    "Context Variable":       ("🔧", "Direct Mapping",   "#e3f2fd", "#1565c0"),
    "Join Key":               ("🔗", "Join",             "#f3e5f5", "#6a1b9a"),
    "Conditional Expression": ("🔀", "Expression",       "#fff8e1", "#f57f17"),
    "String Concatenation":   ("✏️", "Expression",       "#fce4ec", "#880e4f"),
    "Function Transform":     ("🛠️", "Expression",       "#e0f2f1", "#00695c"),
    "Arithmetic Expression":  ("🧮", "Expression",       "#fff3e0", "#bf360c"),
    "Cross-Table Reference":  ("🌐", "Expression",       "#e8eaf6", "#283593"),
    "Expression Mapping":     ("📝", "Expression",       "#f5f5f5", "#424242"),
}

# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<style>
/* ── Lineage Explorer ── */
.le-tab-header{font-size:20px;font-weight:800;color:#1a1a18;margin-bottom:4px;}
.le-sub{font-size:13px;color:#8a8a85;margin-bottom:16px;}
.le-kpi{background:#fff;border:1px solid #e4e3dc;border-left:4px solid #3C3489;
  border-radius:10px;padding:12px 16px;}
.le-kpi-label{font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;
  letter-spacing:.07em;margin-bottom:5px;}
.le-kpi-val{font-size:24px;font-weight:800;color:#3C3489;line-height:1;}
.le-kpi-sub{font-size:11px;color:#8a8a85;margin-top:3px;}
.le-section{font-size:11px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;color:#8a8a85;margin:18px 0 8px;}
.le-view-pill{display:inline-flex;align-items:center;gap:6px;font-size:12px;
  font-weight:600;padding:4px 14px;border-radius:20px;margin-right:6px;
  background:#f1f0eb;color:#3a3a36;cursor:pointer;}
.le-card{background:#fff;border:1px solid #e4e3dc;border-left:4px solid #534AB7;
  border-radius:0 12px 12px 0;padding:12px 18px;margin-top:8px;}
.le-card p{font-size:13px;color:#3a3a36;line-height:1.7;margin:0;}
.le-badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;
  border-radius:20px;margin:0 3px 3px 0;}
.le-lineage-note{font-size:12px;color:#6b6b66;font-style:italic;margin-top:6px;}
.le-flow-legend{display:flex;gap:18px;font-size:11px;color:#6b6b66;margin-top:6px;flex-wrap:wrap;}
.le-flow-legend span{display:flex;align-items:center;gap:4px;}
.le-impact-row{background:#f7f6f1;border-radius:8px;padding:10px 14px;margin-bottom:6px;}
.le-impact-table{font-size:12px;font-weight:700;color:#3C3489;}
.le-impact-fields{font-size:11px;color:#1a1a18;margin-top:2px;}
.le-overview-box{background:#f7f6f1;border:1px solid #e4e3dc;border-radius:10px;
  padding:16px 20px;margin-bottom:12px;}
.le-overview-title{font-size:13px;font-weight:700;color:#3C3489;margin-bottom:6px;}
.le-stat-row{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:10px;}
.le-stat{font-size:12px;color:#3a3a36;}
.le-stat strong{color:#1a1a18;}
.le-col-path{font-family:monospace;font-size:11px;color:#2d2d2a;background:#f0ede6;
  padding:1px 6px;border-radius:4px;}
</style>
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _load_cached(job_name: str, item_path: str):
    return load_mappings({"job_data": {"job_name": job_name}, "file_path": item_path})


def _safe_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name))


def _pill(text: str, bg: str, fg: str) -> str:
    return (
        f'<span class="le-badge" style="background:{bg};color:{fg};">'
        f'{_html.escape(str(text))}</span>'
    )


def _kpi(label: str, value, sub: str, color: str = "#3C3489") -> str:
    return (
        f'<div class="le-kpi" style="border-left-color:{color};">'
        f'<div class="le-kpi-label">{label}</div>'
        f'<div class="le-kpi-val" style="color:{color};">{value}</div>'
        f'<div class="le-kpi-sub">{sub}</div></div>'
    )


def _section(text: str) -> None:
    st.markdown(f'<div class="le-section">{text}</div>', unsafe_allow_html=True)


def _divider() -> None:
    st.markdown(
        "<hr style='border:none;border-top:1px solid #e4e3dc;margin:18px 0;'>",
        unsafe_allow_html=True,
    )


def _empty(msg: str) -> None:
    st.markdown(
        f'<div style="font-size:13px;color:#9e9e96;font-style:italic;padding:10px 0;">'
        f'{msg}</div>',
        unsafe_allow_html=True,
    )


# ── Visual lineage path (single column, vertical chain) ─────────────────────────

def _build_path_chain(
    m: ColumnMapping,
    rule_details: list[MappingRuleDetail],
) -> list[tuple[str, str]]:
    """
    Build the ordered list of (node_id, label) steps for one column mapping,
    e.g. [("src", "CUSTOMERS.CUST_ID"), ("comp", "tMap_1"),
          ("comp", "tFilterRow_1"), ("comp", "tAggregateRow_1"),
          ("tgt", "CUSTOMER_DIM.CUSTOMER_ID")]

    Any Lookup components feeding the same tMap are spliced in ahead of it,
    since they are real intermediate components in the path.
    """
    steps: list[tuple[str, str]] = []

    src_label = ".".join(p for p in (m.source_table, m.source_column) if p) or "—"
    steps.append(("src", src_label))

    lookups_for_tmap = [
        rd.table for rd in rule_details
        if rd.rule_type == "Lookup" and rd.table and rd.table != m.source_table
    ]
    for lk in lookups_for_tmap:
        steps.append(("comp", lk))

    if m.source_component:
        steps.append(("comp", m.source_component))

    tgt_label = ".".join(p for p in (m.target_table, m.target_column) if p) or "—"
    steps.append(("tgt", tgt_label))

    return steps


def _path_chain_to_mermaid(steps: list[tuple[str, str]]) -> str:
    """Render an ordered chain of steps as a vertical Mermaid flowchart (graph TD)."""
    lines = ["graph TD"]
    node_ids = []
    for i, (kind, label) in enumerate(steps):
        nid = f"N{i}_{_safe_id(label)}"
        node_ids.append(nid)
        safe_label = label.replace('"', "'")
        if kind == "src":
            lines.append(f'    {nid}[("📥 {safe_label}")]')
        elif kind == "tgt":
            lines.append(f'    {nid}[("📤 {safe_label}")]')
        else:
            lines.append(f'    {nid}["⚙️ {safe_label}"]')
    for a, b in zip(node_ids, node_ids[1:]):
        lines.append(f"    {a} --> {b}")
    return "\n".join(lines)


def _render_path_chain_text(steps: list[tuple[str, str]]) -> str:
    """Plain-text ↓ rendering of the chain, for copy/paste alongside the diagram."""
    return "\n    ↓\n".join(label for _, label in steps)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

def _render_overview(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    """High-level job data-flow summary with KPIs and flow diagram."""

    st.markdown(
        '<div class="le-overview-title">Job-level data flow at a glance</div>',
        unsafe_allow_html=True,
    )

    # ── KPI strip ─────────────────────────────────────────────────────────────
    n_expr    = sum(1 for m in mappings if m.rule_type == "expression")
    n_tmaps   = len({m.source_component for m in mappings})
    src_tables = sorted({m.source_table for m in mappings if m.source_table})
    tgt_tables = sorted({m.target_table for m in mappings if m.target_table})

    cols = st.columns(5)
    kpi_data = [
        ("Total Mappings",  len(mappings), "columns traced",          "#3C3489"),
        ("Source Tables",   len(src_tables), "distinct inputs",        "#0369a1"),
        ("Target Tables",   len(tgt_tables), "distinct outputs",       "#7c3aed"),
        ("tMap Components", n_tmaps,        "transformers",            "#0891b2"),
        ("Expressions",     n_expr,         "non-direct transforms",   "#e65100"),
    ]
    for col, (lbl, val, sub, color) in zip(cols, kpi_data):
        col.markdown(_kpi(lbl, val, sub, color), unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Rule breakdown ─────────────────────────────────────────────────────────
    _section("📊 Mapping rule breakdown")
    rule_counts: dict[str, int] = defaultdict(int)
    for m in mappings:
        _, lbl, _, _ = RULE_DISPLAY.get(m.rule, ("", m.rule, "", ""))
        rule_counts[lbl] += 1

    if rule_counts:
        df_rules = (
            pd.DataFrame(
                [(lbl, cnt) for lbl, cnt in sorted(rule_counts.items(), key=lambda x: -x[1])],
                columns=["Rule Type", "Count"],
            )
        )
        pct_col = []
        total = df_rules["Count"].sum()
        for cnt in df_rules["Count"]:
            pct_col.append(f"{cnt / total * 100:.0f}%")
        df_rules["Share"] = pct_col
        st.dataframe(df_rules, use_container_width=True, hide_index=True, height=220)
    else:
        _empty("No rule data available.")

    _divider()

    # ── Source → Target summary table ─────────────────────────────────────────
    _section("🗂️ Source → target table pairs")
    if src_tables and tgt_tables:
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        for m in mappings:
            if m.source_table and m.target_table:
                pair_counts[(m.source_table, m.target_table)] += 1

        if pair_counts:
            df_pairs = pd.DataFrame(
                [(s, t, c) for (s, t), c in sorted(pair_counts.items(), key=lambda x: -x[1])],
                columns=["Source Table", "Target Table", "Mapped Columns"],
            )
            st.dataframe(df_pairs, use_container_width=True, hide_index=True, height=260)
        else:
            _empty("No table-pair data could be derived.")
    else:
        _empty("Source or target tables not detected in mappings.")

    _divider()

    # ── Lookup summary ────────────────────────────────────────────────────────
    lookup_tables = [rd for rd in rule_details if rd.rule_type == "Lookup"]
    if lookup_tables:
        _section("🔵 Lookup references")
        lookup_by_table: dict[str, int] = defaultdict(int)
        for rd in lookup_tables:
            lookup_by_table[rd.table] += 1
        df_lk = pd.DataFrame(
            [(t, c) for t, c in sorted(lookup_by_table.items(), key=lambda x: -x[1])],
            columns=["Lookup Table", "References"],
        )
        st.dataframe(df_lk, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 2 — COLUMN LINEAGE
# ══════════════════════════════════════════════════════════════════════════════

def _render_column_lineage(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    """Filterable column-level lineage diagram + detail table."""

    st.caption(
        "End-to-end column flow: source tables → tMap transformations → target tables."
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        search = st.text_input(
            "🔍 Filter columns",
            placeholder="Source or target column name…",
            key=f"_le_lin_search_{job_name}",
            label_visibility="collapsed",
        )
    with fc2:
        src_opts = ["All Sources"] + sorted({m.source_table for m in mappings if m.source_table})
        sel_src = st.selectbox(
            "Source Table",
            src_opts,
            key=f"_le_lin_src_{job_name}",
            label_visibility="collapsed",
        )
    with fc3:
        tgt_opts = ["All Targets"] + sorted({m.target_table for m in mappings if m.target_table})
        sel_tgt = st.selectbox(
            "Target Table",
            tgt_opts,
            key=f"_le_lin_tgt_{job_name}",
            label_visibility="collapsed",
        )

    # Apply filters
    filtered = mappings
    if search:
        q = search.lower()
        filtered = [
            m for m in filtered
            if q in (m.source_column or "").lower()
            or q in (m.target_column or "").lower()
        ]
    if sel_src != "All Sources":
        filtered = [m for m in filtered if m.source_table == sel_src]
    if sel_tgt != "All Targets":
        filtered = [m for m in filtered if m.target_table == sel_tgt]

    st.caption(f"Showing **{len(filtered)}** of **{len(mappings)}** mappings")

    _divider()

    # ── Mermaid lineage diagram ────────────────────────────────────────────────
    _section("🔄 Data lineage diagram")

    if len(filtered) > LINEAGE_MAX_MAPPINGS:
        st.warning(
            f"Diagram limited to {LINEAGE_MAX_MAPPINGS} mappings — "
            f"use filters above to narrow the view. Showing detail table only."
        )
    else:
        lines = ["graph LR"]

        src_tables   = sorted({m.source_table  for m in filtered if m.source_table})
        tmap_names   = sorted({m.source_component for m in filtered})
        tgt_tables   = sorted({m.target_table   for m in filtered if m.target_table})
        lookup_tbls  = sorted({rd.table for rd in rule_details if rd.rule_type == "Lookup"})

        for t in src_tables:
            lines.append(f'    SRC_{_safe_id(t)}[("📥 {t}")]')
        for n in tmap_names:
            n_expr = sum(1 for m in filtered if m.source_component == n and m.rule_type == "expression")
            label  = f"⚙️ {n}\\n{n_expr} expr" if n_expr else f"🗺️ {n}"
            lines.append(f'    TMAP_{_safe_id(n)}["{label}"]')
        for t in tgt_tables:
            lines.append(f'    TGT_{_safe_id(t)}[("📤 {t}")]')
        for lk in lookup_tbls:
            if lk not in src_tables:
                lines.append(f'    LKP_{_safe_id(lk)}[("🔵 {lk}")]')

        pairs_seen: set[tuple] = set()
        for m in filtered:
            if m.source_table and m.source_component:
                key = (m.source_table, m.source_component)
                if key not in pairs_seen:
                    pairs_seen.add(key)
                    cnt = sum(
                        1 for x in filtered
                        if x.source_table == m.source_table
                        and x.source_component == m.source_component
                    )
                    lines.append(
                        f'    SRC_{_safe_id(m.source_table)} -->|"{cnt} cols"| TMAP_{_safe_id(m.source_component)}'
                    )

        tmap_tgt_seen: set[tuple] = set()
        for m in filtered:
            if m.source_component and m.target_table:
                key = (m.source_component, m.target_table)
                if key not in tmap_tgt_seen:
                    tmap_tgt_seen.add(key)
                    n_expr_edge = sum(
                        1 for x in filtered
                        if x.source_component == m.source_component
                        and x.target_table == m.target_table
                        and x.rule_type == "expression"
                    )
                    lbl = "🔀 expr" if n_expr_edge else "→"
                    lines.append(
                        f'    TMAP_{_safe_id(m.source_component)} -->|"{lbl}"| TGT_{_safe_id(m.target_table)}'
                    )

        lkp_seen: set[tuple] = set()
        for rd in rule_details:
            if rd.rule_type == "Lookup" and rd.table:
                for tn in tmap_names:
                    key = (rd.table, tn)
                    if key not in lkp_seen:
                        lkp_seen.add(key)
                        lines.append(
                            f'    LKP_{_safe_id(rd.table)} -.->|"lookup"| TMAP_{_safe_id(tn)}'
                        )

        if len(lines) > 1:
            render_mermaid_diagram("\n".join(lines), height=380)
        else:
            _empty("No lineage could be determined from the current filter.")

        st.markdown(
            '<div class="le-lineage-note">Solid arrows = data flow. '
            'Dashed arrows = lookup references.</div>',
            unsafe_allow_html=True,
        )

    _divider()

    # ── Column-level detail table ──────────────────────────────────────────────
    _section("📋 Column lineage detail")

    if filtered:
        rows = []
        for m in filtered:
            ico, lbl, _, _ = RULE_DISPLAY.get(m.rule, ("📝", m.rule, "#f5f5f5", "#424242"))
            rows.append({
                "Source Table":     m.source_table or "—",
                "Source Column":    m.source_column or "—",
                "tMap":             m.source_component or "—",
                "Rule":             f"{ico} {lbl}",
                "Target Table":     m.target_table or "—",
                "Target Column":    m.target_column or "—",
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)

        _divider()

        # ── Visual lineage path for a single selected mapping ───────────────────
        _section("🧭 Visual lineage path")
        _path_opts = {
            f"{m.source_table or '—'}.{m.source_column or '—'} → {m.target_table or '—'}.{m.target_column or '—'}": m
            for m in filtered
        }
        _path_choice = st.selectbox(
            "Select a column mapping to trace",
            list(_path_opts.keys()),
            key=f"_le_path_pick_{job_name}",
        )
        if _path_choice:
            _m = _path_opts[_path_choice]
            _lookup_rds = [rd for rd in rule_details if rd.rule_type == "Lookup"]
            _steps = _build_path_chain(_m, rule_details=_lookup_rds)
            render_mermaid_diagram(_path_chain_to_mermaid(_steps), height=60 + 90 * len(_steps))
            st.code(_render_path_chain_text(_steps), language=None)
    else:
        _empty("No mappings match the current filters.")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 3 — IMPACT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def _render_impact_analysis(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    """Select a target column and trace everything that feeds it upstream."""

    st.caption(
        "Select a target column to trace all source fields, tables and "
        "transformations that contribute to it."
    )

    target_cols = sorted({m.target_column for m in mappings if m.target_column})
    if not target_cols:
        _empty("No target columns found in this job.")
        return

    sel = st.selectbox(
        "🎯 Target Column",
        target_cols,
        key=f"_le_impact_sel_{job_name}",
    )

    related = [m for m in mappings if m.target_column == sel]
    src_tables  = sorted({m.source_table for m in related})
    rule_types  = sorted({RULE_DISPLAY.get(m.rule, ("", m.rule, "", ""))[1] for m in related})
    n_expr      = sum(1 for m in related if m.rule_type == "expression")
    src_fields  = [(m.source_table, m.source_column) for m in related]

    # KPI row
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(_kpi("Source Fields",  len(src_fields),  "feeding this column",    "#3C3489"), unsafe_allow_html=True)
    k2.markdown(_kpi("Source Tables",  len(src_tables),  "input tables",           "#0369a1"), unsafe_allow_html=True)
    k3.markdown(_kpi("Rule Types",     len(rule_types),  "unique rule categories", "#2e7d32"), unsafe_allow_html=True)
    k4.markdown(_kpi("Expressions",    n_expr,           "non-direct transforms",  "#e65100"), unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _divider()

    # ── Visual lineage path (Mermaid, one chain per source → target hop) ────────
    _section("🧭 Visual lineage path")
    if related:
        for i, m in enumerate(related):
            tmap_rule_details = [rd for rd in rule_details if rd.rule_type == "Lookup"]
            steps = _build_path_chain(m, rule_details=tmap_rule_details)
            chain_label = " → ".join(label for _, label in steps)
            with st.expander(chain_label, expanded=(i == 0)):
                render_mermaid_diagram(_path_chain_to_mermaid(steps), height=60 + 90 * len(steps))
                st.code(_render_path_chain_text(steps), language=None)
    else:
        _empty("No path available for this column.")

    _divider()

    # ── Upstream lineage ───────────────────────────────────────────────────────
    _section("📥 Upstream sources")
    for tbl in src_tables:
        fields = [m.source_column for m in related if m.source_table == tbl]
        badges = "".join(_pill(f, "#e3f2fd", "#1565c0") for f in fields)
        st.markdown(
            f'<div class="le-impact-row">'
            f'<div class="le-impact-table">📥 {_html.escape(tbl)}</div>'
            f'<div class="le-impact-fields">{badges}</div></div>',
            unsafe_allow_html=True,
        )

    _divider()

    # ── Transformation detail cards ────────────────────────────────────────────
    _section("🔀 Transformation rules applied")
    for m in related:
        ico, lbl, bg, fg = RULE_DISPLAY.get(m.rule, ("📝", m.rule, "#f5f5f5", "#424242"))
        has_expr = bool(getattr(m, "expression", None))
        card = (
            f'<div class="le-card" style="border-left-color:{fg};background:{bg};">'
            f'<p><strong>{ico} {lbl}</strong> — '
            f'{_html.escape(m.source_component)}: '
            f'<span class="le-col-path">{_html.escape(m.source_table or "")}.{_html.escape(m.source_column or "")}</span>'
            f' → '
            f'<span class="le-col-path">{_html.escape(m.target_column or "")}</span>'
        )
        if has_expr:
            card += (
                f'<br><span style="font-size:11px;font-family:monospace;color:#374151;">'
                f'{_html.escape(str(m.expression))}</span>'
            )
        card += "</p></div>"
        st.markdown(card, unsafe_allow_html=True)

    _divider()

    # ── Downstream: what other targets share the same sources? ─────────────────
    _section("📤 Sibling targets (share same source fields)")
    sibling_map: dict[str, set[str]] = defaultdict(set)
    for src_tbl, src_col in src_fields:
        for m in mappings:
            if (
                m.source_table == src_tbl
                and m.source_column == src_col
                and m.target_column != sel
            ):
                sibling_map[f"{src_tbl}.{src_col}"].add(m.target_column)

    if sibling_map:
        rows = []
        for src_path, siblings in sorted(sibling_map.items()):
            rows.append({
                "Source Field":   src_path,
                "Also Feeds":     ", ".join(sorted(siblings)),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "These target columns share at least one source field with the selected column. "
            "Changes upstream may affect them too."
        )
    else:
        _empty("No sibling targets found — this column has exclusive source fields.")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 4 — SOURCE COLUMN EXPLORER  (powered by trace_forward)
# ══════════════════════════════════════════════════════════════════════════════

def _render_source_column_explorer(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    """Select a source column; trace_forward() reveals all downstream impact."""

    st.caption("Select a source column to trace every downstream table, column and job affected by it.")

    src_options = sorted({
        f"{m.source_table or '—'}.{m.source_column or '—'}"
        for m in mappings if m.source_column
    })
    if not src_options:
        _empty("No source columns found in this job.")
        return

    sel = st.selectbox(
        "📥 Source Column",
        src_options,
        key=f"_le_sce_sel_{job_name}",
    )

    sel_table, sel_col = (sel.split(".", 1) + [""])[:2]

    # ── Build graph and run trace_forward ────────────────────────────────────
    graph = build_graph(mappings, rule_details, job_name=job_name)
    if graph.is_empty:
        _empty("Lineage graph is empty for this job. No lineage available.")
        return
    start_id = _source_node_id(job_name, sel_table, sel_col)

    if not graph.has_node(start_id):
        _empty(f"Node `{start_id}` not found in graph. No lineage available.")
        return

    result = trace_forward(graph, start_id)

    # ── Aggregate impact ──────────────────────────────────────────────────────
    affected_tables:  set[str] = set()
    affected_columns: set[str] = set()
    affected_jobs:    set[str] = set()

    for node in graph.nodes:
        if node.id in result.visited_nodes and node.id != start_id:
            if node.node_type in (NodeType.TARGET_TABLE, NodeType.SOURCE_TABLE):
                t = node.metadata.get("table") or node.table
                c = node.metadata.get("column", "")
                if t:
                    affected_tables.add(t)
                if c:
                    affected_columns.add(f"{t}.{c}" if t else c)
            if node.job_name and node.job_name != job_name:
                affected_jobs.add(node.job_name)

    # Fallback: derive from direct mappings when graph yields nothing
    direct = [m for m in mappings if (m.source_table or "—") == sel_table and (m.source_column or "—") == sel_col]
    if not affected_tables:
        affected_tables  = {m.target_table for m in direct if m.target_table}
        affected_columns = {f"{m.target_table}.{m.target_column}" for m in direct if m.target_column}

    n_paths      = len(result.paths) + len(result.truncated_paths)
    n_hops_max   = max((p.hop_count for p in result.all_paths), default=0)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(_kpi("Affected Tables",  len(affected_tables),  "downstream tables",    "#3C3489"), unsafe_allow_html=True)
    k2.markdown(_kpi("Affected Columns", len(affected_columns), "target columns",       "#7c3aed"), unsafe_allow_html=True)
    k3.markdown(_kpi("Affected Jobs",    max(len(affected_jobs), 1), "jobs impacted",   "#0369a1"), unsafe_allow_html=True)
    k4.markdown(_kpi("Lineage Paths",    n_paths,               f"max {n_hops_max} hops", "#e65100"), unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    _divider()

    # ── Affected Tables ────────────────────────────────────────────────────────
    _section("📋 Affected Tables")
    if affected_tables:
        tbl_rows = []
        for t in sorted(affected_tables):
            cols_for_t = sorted(c.split(".", 1)[1] for c in affected_columns if c.startswith(f"{t}."))
            tbl_rows.append({"Target Table": t, "Columns Affected": len(cols_for_t), "Columns": ", ".join(cols_for_t) or "—"})
        st.dataframe(pd.DataFrame(tbl_rows), use_container_width=True, hide_index=True)
    else:
        _empty("No downstream tables identified.")

    _divider()

    # ── Affected Columns ───────────────────────────────────────────────────────
    _section("🔢 Affected Columns")
    if affected_columns:
        col_rows = []
        for fc in sorted(affected_columns):
            parts = fc.split(".", 1)
            t, c = (parts[0], parts[1]) if len(parts) == 2 else ("—", fc)
            rule_lbl = "—"
            for m in direct:
                if m.target_table == t and m.target_column == c:
                    ico, lbl, _, _ = RULE_DISPLAY.get(m.rule, ("📝", m.rule, "", ""))
                    rule_lbl = f"{ico} {lbl}"
                    break
            col_rows.append({"Table": t, "Column": c, "Rule": rule_lbl})
        st.dataframe(pd.DataFrame(col_rows), use_container_width=True, hide_index=True, height=min(400, 40 + 35 * len(col_rows)))
    else:
        _empty("No downstream columns identified.")

    _divider()

    # ── Affected Jobs ──────────────────────────────────────────────────────────
    _section("💼 Affected Jobs")
    if affected_jobs:
        st.dataframe(pd.DataFrame({"Job Name": sorted(affected_jobs)}), use_container_width=True, hide_index=True)
    else:
        st.markdown(
            '<div class="le-impact-row"><div class="le-impact-table">Current job only</div>'
            '<div class="le-impact-fields">'
            + _pill(job_name, "#e3f2fd", "#1565c0") +
            '</div></div>',
            unsafe_allow_html=True,
        )

    _divider()

    # ── Traversal paths ────────────────────────────────────────────────────────
    if result.paths or result.truncated_paths:
        _section("🧭 Forward Lineage Paths")
        if result.has_cycles:
            st.warning(f"⚠️ {len(result.cycles_detected)} cycle(s) detected and terminated during traversal.")
        for i, path in enumerate(result.all_paths[:10]):
            labels = [n.label or n.id for n in path.nodes]
            title  = " → ".join(labels)
            with st.expander(f"Path {i+1}  ({path.hop_count} hop{'s' if path.hop_count != 1 else ''}): {title[:80]}", expanded=(i == 0)):
                steps = [(("src" if n.node_type == NodeType.SOURCE_TABLE else "tgt" if n.node_type == NodeType.TARGET_TABLE else "comp"), n.label or n.id) for n in path.nodes]
                render_mermaid_diagram(_path_chain_to_mermaid(steps), height=60 + 90 * len(steps))



# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

# ── Lineage Search ────────────────────────────────────────────────────────────

def _search_lineage_nodes(graph: LineageGraph, query: str) -> list[LineageNode]:
    """Return nodes in *graph* whose label, table, or component matches *query*."""
    q = query.strip().lower()
    if not q:
        return []
    results: list[LineageNode] = []
    for node in graph.nodes:
        t     = (node.table or node.metadata.get("table", "")).lower()
        lbl   = (node.label or "").lower()
        cname = (node.component_name or "").lower()
        cols  = set()
        for e in graph.edges_from(node.id) + graph.edges_to(node.id):
            if e.source_column:
                cols.add(e.source_column.lower())
            if e.target_column:
                cols.add(e.target_column.lower())
        if q in t or q in lbl or q in cname or any(q in c for c in cols):
            results.append(node)
    return results


def _render_lineage_search(graph: LineageGraph, job_name: str) -> None:
    """🔎 Lineage Search view: find any node by table/column/component name."""
    _section("🔎 Lineage Search")

    query = st.text_input(
        "Search tables, columns, or components",
        key=f"_le_search_q_{job_name}",
        placeholder="e.g. customer_id, tMap_1, CUSTOMERS",
    )

    if not query:
        _empty("Type a table, column, or component name to search this job's lineage.")
        return

    hits = _search_lineage_nodes(graph, query)
    if not hits:
        _empty(f"No nodes matched “{query}”.")
        return

    st.markdown(f"**{len(hits)}** match(es) for “{query}”")

    for node in hits:
        cols = st.columns([5, 2])
        with cols[0]:
            st.markdown(
                _pill(node.node_type.value, "#ede9fe", "#5b21b6")
                + " "
                + _pill(node.label or node.id, "#e0f2fe", "#0369a1"),
                unsafe_allow_html=True,
            )
        with cols[1]:
            if st.button("View details", key=f"_le_search_view_{job_name}_{_safe_id(node.id)}"):
                st.session_state[f"_le_detail_node_{job_name}"] = node.id
        _divider()

    selected_id = st.session_state.get(f"_le_detail_node_{job_name}")
    if selected_id:
        selected = graph.get_node(selected_id)
        if selected:
            _render_node_details(graph, selected, job_name)


# ── Node Details ──────────────────────────────────────────────────────────────

def _render_node_details(graph: LineageGraph, node: LineageNode, job_name: str) -> None:
    """Show a detail panel for a single lineage node: metadata + connections."""
    _section(f"📌 Node details — {node.label or node.id}")

    meta_html = "".join(
        f'<div class="le-meta-row"><b>{_html.escape(k)}:</b> {_html.escape(str(v))}</div>'
        for k, v in [
            ("Type", node.node_type.value),
            ("Job", node.job_name),
            ("System", node.system_type),
            ("Database", node.database),
            ("Schema", node.schema),
            ("Table", node.table),
            ("Component", node.component_name),
            ("Component type", node.component_type),
            ("Physical identity", node.physical_identity),
        ]
        if v
    )
    st.markdown(meta_html or "<i>No metadata available.</i>", unsafe_allow_html=True)

    in_edges  = graph.edges_to(node.id)
    out_edges = graph.edges_from(node.id)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Incoming edges ({len(in_edges)})**")
        for e in in_edges:
            src = graph.get_node(e.source_node_id)
            st.markdown(f"- {src.label if src else e.source_node_id} → *{e.edge_type.value}*")
    with c2:
        st.markdown(f"**Outgoing edges ({len(out_edges)})**")
        for e in out_edges:
            tgt = graph.get_node(e.target_node_id)
            st.markdown(f"- *{e.edge_type.value}* → {tgt.label if tgt else e.target_node_id}")

    if st.button("✖ Close details", key=f"_le_detail_close_{job_name}_{_safe_id(node.id)}"):
        st.session_state.pop(f"_le_detail_node_{job_name}", None)
        st.rerun()


# ── Path Highlight ────────────────────────────────────────────────────────────

def _highlight_mermaid_for_path(steps: list[tuple[str, str]], highlight_ids: set[str]) -> str:
    """
    Build a Mermaid flowchart of *steps* (id, label) with nodes in
    *highlight_ids* rendered in a distinct highlight style.
    """
    lines = ["flowchart LR"]
    for nid, label in steps:
        safe = _safe_id(nid)
        lines.append(f'{safe}["{label}"]')
    for (a, _), (b, _) in zip(steps, steps[1:]):
        lines.append(f"{_safe_id(a)} --> {_safe_id(b)}")
    for nid, _ in steps:
        if nid in highlight_ids:
            lines.append(f"style {_safe_id(nid)} fill:#fde68a,stroke:#b45309,stroke-width:2px")
    return "\n".join(lines)


def _render_path_highlight(graph: LineageGraph, job_name: str) -> None:
    """🛣️ Path Highlight view: trace and visually highlight one node's full path."""
    _section("🛣️ Path Highlight")

    node_options = {f"{n.label or n.id}  ({n.node_type.value})": n.id for n in graph.nodes}
    if not node_options:
        _empty("No nodes available to trace in this job.")
        return

    sel_label = st.selectbox(
        "Select a node to trace its full upstream + downstream path",
        sorted(node_options),
        key=f"_le_highlight_sel_{job_name}",
    )
    node_id = node_options[sel_label]

    upstream   = trace_backward(graph, node_id)
    downstream = trace_forward(graph, node_id)

    path_ids: list[str] = []
    for p in sorted(upstream.all_paths, key=lambda p: -p.hop_count)[:1]:
        path_ids.extend(n.id for n in p.nodes)
    if not path_ids:
        path_ids = [node_id]
    for p in sorted(downstream.all_paths, key=lambda p: -p.hop_count)[:1]:
        path_ids.extend(n.id for n in p.nodes[1:])

    seen = set()
    steps: list[tuple[str, str]] = []
    for nid in path_ids:
        if nid in seen:
            continue
        seen.add(nid)
        n = graph.get_node(nid)
        steps.append((nid, n.label or nid if n else nid))

    if len(steps) < 2:
        _empty("No connected path found for this node.")
        return

    mermaid = _highlight_mermaid_for_path(steps, {node_id})
    render_mermaid_diagram(mermaid)

    n_up   = len(upstream.visited_nodes) - 1
    n_down = len(downstream.visited_nodes) - 1
    st.caption(f"{n_up} upstream node(s) · {n_down} downstream node(s) from **{sel_label}**")


def render_lineage_explorer_tab(
    job: dict,
    jd: dict,
    inv: dict,
    all_jobs: list,
    job_name: str,
) -> None:
    """Render the 🧭 Lineage Explorer tab inside Job 360 Analysis."""

    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown(
        '<div class="le-tab-header">🧭 Lineage Explorer</div>'
        '<div class="le-sub">End-to-end data lineage, column-level flow tracing '
        'and impact analysis for this job.</div>',
        unsafe_allow_html=True,
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    job_path = job.get("file_path", "")
    mappings, rule_details = _load_cached(job_name, job_path)

    if not mappings:
        return

    # ── Export section ────────────────────────────────────────────────────────
    _section("📤 Export")
    _export_graph = build_graph(mappings, rule_details, job_name=job_name)
    _exp_json, _exp_graphml, _exp_csv = st.columns(3)
    with _exp_json:
        st.download_button(
            "📥 Export JSON",
            data=_export_graph.to_json(),
            file_name=f"{job_name}_lineage.json",
            mime="application/json",
            key=f"_le_export_json_{job_name}",
            use_container_width=True,
        )
    with _exp_graphml:
        st.download_button(
            "📊 Export GraphML",
            data=_export_graph.to_graphml(),
            file_name=f"{job_name}_lineage.graphml",
            mime="application/xml",
            key=f"_le_export_graphml_{job_name}",
            use_container_width=True,
        )
    with _exp_csv:
        st.download_button(
            "📄 Export CSV",
            data=_export_graph.to_csv(),
            file_name=f"{job_name}_lineage.csv",
            mime="text/csv",
            key=f"_le_export_csv_{job_name}",
            use_container_width=True,
        )

    _divider()

    # ── View switcher ─────────────────────────────────────────────────────────
    view = st.radio(
        "View",
        ["📊 Overview", "🔗 Column Lineage", "🎯 Impact Analysis", "🔎 Source Column Explorer",
         "🔍 Lineage Search", "🛣️ Path Highlight"],
        horizontal=True,
        key=f"_le_view_{job_name}",
    )

    _divider()

    if view == "📊 Overview":
        _render_overview(mappings, rule_details, job_name)
    elif view == "🔗 Column Lineage":
        _render_column_lineage(mappings, rule_details, job_name)
    elif view == "🎯 Impact Analysis":
        _render_impact_analysis(mappings, rule_details, job_name)
    elif view == "🔍 Lineage Search":
        _render_lineage_search(_export_graph, job_name)
    elif view == "🛣️ Path Highlight":
        _render_path_highlight(_export_graph, job_name)
    else:
        _render_source_column_explorer(mappings, rule_details, job_name)
