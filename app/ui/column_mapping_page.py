"""
Column Mapping Tab — Job 360 Analysis
Renders the Column Mapping tab inside render_job_analysis_page().

Phases implemented:
  P6  – Empty page shell
  P7  – Tab registration (wired in job_analysis_page.py)
  P8  – ColumnMapping data model (column_mapping_model.py)
  P9  – DTOs (column_mapping_dto.py)
  P10 – Service layer (column_mapping_service.py)
  P11 – Direct mappings grid
  P12 – Expression mappings
  P13 – Lookup mappings
  P14 – Join mappings
  P15 – Output mappings
  P16 – Unified mapping grid
  P17 – Sorting
  P18 – Pagination
  P19 – Responsive layout
  P20 – Search box
  P21 – Component dropdown
  P22 – Source table filter
  P23 – Target table filter
  P24–P28 – tMap drilldown
  P29–P32 – Transformation view
  P33–P37 – Visual lineage
  P38–P41 – Impact analysis
  P42–P46 – Source-target matrix
  P47–P50 – AI explanation
  P51–P54 – Exports
  P55–P59 – Polish & optimisation
"""

from __future__ import annotations

import io
import re
import json
import html as _html
from collections import OrderedDict

try:
    import pandas as pd
except ModuleNotFoundError:
    class _MiniDataFrame(list):
        def __init__(self, data=None, *args, **kwargs):
            super().__init__(data or [])

        @property
        def empty(self):
            return len(self) == 0

        def to_dict(self, *args, **kwargs):
            return list(self)

    class _MiniPandas:
        DataFrame = _MiniDataFrame

    pd = _MiniPandas()

try:
    import streamlit as st
    from streamlit.components.v1 import html as components_html
except ModuleNotFoundError:
    class _StreamlitShim:
        session_state = {}

        def cache_data(self, *args, **kwargs):
            return lambda fn: fn

        def __getattr__(self, name):
            if name in {"columns", "tabs"}:
                return lambda *args, **kwargs: [self for _ in range(len(args[0]) if args and isinstance(args[0], (list, tuple)) else 1)]
            return lambda *args, **kwargs: None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    st = _StreamlitShim()

    def components_html(*args, **kwargs):
        return None

from app.ui.column_mapping_service import load_mappings
from app.ui.column_mapping_model import ColumnMapping, MappingRuleDetail
from app.ui.design_system_v2 import render_mermaid_diagram, pdf_download_button

# ── Constants ─────────────────────────────────────────────────────────────────
PAGE_SIZE = 50
MAX_TMAP_EXPANDERS = 20
MAX_EXPR_DETAIL = 50
LINEAGE_MAX_MAPPINGS = 200


@st.cache_data(show_spinner=False)
def _load_mappings_cached(job_name: str, item_path: str):
    return load_mappings({"job_data": {"job_name": job_name}, "file_path": item_path})

# ── Rule display config ───────────────────────────────────────────────────────
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

RULE_TYPE_MAP = {
    "Direct Copy":            "direct",
    "Direct Copy (Nullable)": "direct",
    "Type Cast":              "direct",
    "Context Variable":       "direct",
    "Join Key":               "join",
    "Conditional Expression": "expression",
    "String Concatenation":   "expression",
    "Function Transform":     "expression",
    "Arithmetic Expression":  "expression",
    "Cross-Table Reference":  "expression",
    "Expression Mapping":     "expression",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", str(name))


def _pill(text: str, bg: str, fg: str) -> str:
    return (
        f'<span style="background:{bg};color:{fg};font-size:11px;font-weight:700;'
        f'padding:2px 10px;border-radius:20px;margin:0 3px 3px 0;">{_html.escape(str(text))}</span>'
    )


def _section_label(text: str) -> None:
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;letter-spacing:.08em;'
        f'text-transform:uppercase;color:#8a8a85;margin:16px 0 8px;">{text}</div>',
        unsafe_allow_html=True,
    )


def _kpi_card(label: str, value, sub: str, color: str = "#3C3489") -> str:
    return (
        f'<div style="background:#fff;border:1px solid #e4e3dc;border-left:4px solid {color};'
        f'border-radius:10px;padding:12px 16px;">'
        f'<div style="font-size:11px;font-weight:700;color:#8a8a85;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:5px;">{label}</div>'
        f'<div style="font-size:24px;font-weight:800;color:{color};line-height:1;">{value}</div>'
        f'<div style="font-size:11px;color:#8a8a85;margin-top:3px;">{sub}</div></div>'
    )


def _empty_state(msg: str) -> None:
    st.markdown(
        f'<div style="font-size:13px;color:#9e9e96;font-style:italic;'
        f'padding:12px 0;">{msg}</div>',
        unsafe_allow_html=True,
    )


def _divider() -> None:
    st.markdown("<hr style='border:none;border-top:1px solid #e4e3dc;margin:18px 0;'>",
                unsafe_allow_html=True)
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


# ── Build display DataFrame ───────────────────────────────────────────────────

def _build_df(mappings: list[ColumnMapping]) -> pd.DataFrame:
    rows = []
    for m in mappings:
        ico, lbl, _, _ = RULE_DISPLAY.get(m.rule, ("📝", m.rule, "#f5f5f5", "#424242"))
        rows.append({
            "Source Component": m.source_component,
            "Source Table":     m.source_table,
            "Source Column":    m.source_column,
            "Target Table":     m.target_table,
            "Target Column":    m.target_column,
            "Rule":             lbl,
            "_raw_rule":        m.rule,
            "_expression":      m.expression,
            "_rule_type":       m.rule_type,
        })
    return pd.DataFrame(rows)


def _source_table_names_from_inventory(inv: dict) -> list[str]:
    names = []
    seen = set()
    for src in inv.get("sources", []) if isinstance(inv, dict) else []:
        name = str(src.get("qualified_name") or src.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _display_mappings(mappings: list[ColumnMapping], inv: dict) -> list[ColumnMapping]:
    source_tables = _source_table_names_from_inventory(inv)
    if len(source_tables) != 1:
        return mappings

    resolved_source = source_tables[0]
    remapped = []
    for m in mappings:
        remapped.append(ColumnMapping(
            source_component=m.source_component,
            source_table=resolved_source,
            source_column=m.source_column,
            target_component=m.target_component,
            target_table=m.target_table,
            target_column=m.target_column,
            rule=m.rule,
            expression=m.expression,
            rule_type=m.rule_type,
        ))
    return remapped


# ── CSS injected once ─────────────────────────────────────────────────────────

_CSS = """
<style>
.cm-badge{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;border-radius:20px;margin:0 3px 3px 0;}
.cm-kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px;}
.cm-filter-row{display:flex;align-items:flex-end;gap:10px;margin-bottom:10px;flex-wrap:wrap;}
.cm-tmap-header{font-size:13px;font-weight:700;color:#3C3489;margin-bottom:4px;}
.cm-tmap-sub{font-size:11px;color:#8a8a85;}
.cm-expr-card{background:#f7f6f1;border-radius:8px;padding:10px 14px;margin-bottom:8px;}
.cm-expr-target{font-size:12px;font-weight:700;color:#3C3489;margin-bottom:4px;}
.cm-expr-text{font-family:monospace;font-size:11px;color:#2d2d2a;word-break:break-all;}
.cm-lineage-note{font-size:12px;color:#6b6b66;font-style:italic;margin-top:4px;}
.cm-pitch{background:#fff;border:1px solid #e4e3dc;border-left:4px solid #534AB7;
  border-radius:0 12px 12px 0;padding:12px 18px;margin-top:10px;}
.cm-pitch p{font-size:13px;color:#3a3a36;line-height:1.7;margin:0;}
</style>
"""


# ── Main render function ──────────────────────────────────────────────────────

def render_column_mapping_tab(
    job: dict,
    jd: dict,
    inv: dict,
    all_jobs: list,
    job_name: str,
) -> None:
    """Render the Column Mapping tab inside Job 360 Analysis."""

    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    job_path = job.get("file_path", "")
    mappings, rule_details = _load_mappings_cached(job_name, job_path)
    mappings = _display_mappings(mappings, inv)

    st.info(f"Job Name: {job_name}")
    st.info(f"Job Path: {job_path or 'Not available'}")
    st.info("load_mappings() called successfully")
    st.info(f"Mapping Count: {len(mappings)}")
    st.info(f"Rule Count: {len(rule_details)}")

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown(
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">'
        '<span style="font-size:20px;font-weight:800;color:#1a1a18;">🗺️ Column Mapping</span>'
        '</div>'
        '<div style="font-size:13px;color:#8a8a85;margin-bottom:14px;">'
        'tMap column-level mapping, transformations, lineage and impact analysis.</div>',
        unsafe_allow_html=True,
    )

    if not mappings:
        st.info(
            "No column mappings found for this job. "
            "This may mean the .item file is not accessible, "
            "or the job contains no tMap components."
        )
        _render_rule_details_only(rule_details, job_name)
        return

    # ── KPI strip ─────────────────────────────────────────────────────────────
    n_direct = sum(1 for m in mappings if m.rule_type == "direct")
    n_expr   = sum(1 for m in mappings if m.rule_type == "expression")
    n_join   = sum(1 for m in mappings if m.rule_type == "join")
    n_lookup = sum(1 for rd in rule_details if rd.rule_type == "Lookup")
    n_tmaps  = len({m.source_component for m in mappings})

    kpi_cols = st.columns(4)
    kpi_data = [
        ("Total Mappings", len(mappings), "across all tMap components", "#3C3489"),
        ("Direct",         n_direct,      "copy / type-cast",           "#2e7d32"),
        ("Expression",     n_expr,        "transform / conditional",     "#e65100"),
        ("tMap Components",n_tmaps,       "components analysed",         "#0369a1"),
    ]
    for col, (lbl, val, sub, color) in zip(kpi_cols, kpi_data):
        col.markdown(_kpi_card(lbl, val, sub, color), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── View mode ─────────────────────────────────────────────────────────────
    view_mode = st.radio(
        "View",
        ["📋 Mapping Grid", "🔢 Source-Target Matrix"],
        horizontal=True,
        key=f"_colmap_view_{job_name}",
    )

    _divider()

    if view_mode == "📋 Mapping Grid":
        _render_mapping_grid(mappings, rule_details, job_name)
    else:
        _render_matrix(mappings, job_name)

    _divider()
    _render_tmap_drilldown(mappings, rule_details, job_name)
    _divider()
    _render_lineage(mappings, rule_details, job_name)
    _divider()
    _render_impact_analysis(mappings, job_name)
    _divider()
    _render_ai_explanation(mappings, job_name)
    _divider()
    _render_exports(mappings, rule_details, job_name)


# ── Mapping Grid ──────────────────────────────────────────────────────────────

def _render_mapping_grid(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    _section_label("📋 Column Mapping Grid")
    st.caption("All column-level mappings extracted from tMap components.")

    df_all = _build_df(mappings)

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4 = st.columns([2, 1, 1, 1])
    with fc1:
        search_query = st.text_input(
            "🔍 Search",
            placeholder="Source column, target column, or rule…",
            key=f"_colmap_search_{job_name}",
            label_visibility="collapsed",
        )
    with fc2:
        comp_opts = ["All Components"] + sorted(df_all["Source Component"].unique())
        sel_comp = st.selectbox(
            "Component", comp_opts,
            key=f"_colmap_comp_{job_name}", label_visibility="collapsed",
        )
    with fc3:
        src_tbl_opts = ["All Source Tables"] + sorted(df_all["Source Table"].unique())
        sel_src_tbl = st.selectbox(
            "Source Table", src_tbl_opts,
            key=f"_colmap_srctbl_{job_name}", label_visibility="collapsed",
        )
    with fc4:
        tgt_tbl_opts = ["All Target Tables"] + sorted(df_all["Target Table"].unique())
        sel_tgt_tbl = st.selectbox(
            "Target Table", tgt_tbl_opts,
            key=f"_colmap_tgttbl_{job_name}", label_visibility="collapsed",
        )

    # ── Sort ──────────────────────────────────────────────────────────────────
    sc1, sc2 = st.columns([2, 6])
    with sc1:
        sort_by = st.selectbox(
            "Sort by",
            ["Source Column", "Target Column", "Rule", "Source Component"],
            key=f"_colmap_sort_{job_name}",
        )

    # ── Apply filters ─────────────────────────────────────────────────────────
    df = df_all.copy()
    if search_query:
        mask = (
            df["Source Column"].str.contains(search_query, case=False, na=False) |
            df["Target Column"].str.contains(search_query, case=False, na=False) |
            df["Rule"].str.contains(search_query, case=False, na=False)
        )
        df = df[mask]
    if sel_comp != "All Components":
        df = df[df["Source Component"] == sel_comp]
    if sel_src_tbl != "All Source Tables":
        df = df[df["Source Table"] == sel_src_tbl]
    if sel_tgt_tbl != "All Target Tables":
        df = df[df["Target Table"] == sel_tgt_tbl]

    df = df.sort_values(sort_by, na_position="last")

    # Active filters count
    active_filters = sum([
        bool(search_query),
        sel_comp != "All Components",
        sel_src_tbl != "All Source Tables",
        sel_tgt_tbl != "All Target Tables",
    ])
    if active_filters:
        st.markdown(
            f'<span class="cm-badge" style="background:#EEEDFE;color:#3C3489;">'
            f'{active_filters} filter{"s" if active_filters > 1 else ""} active</span>',
            unsafe_allow_html=True,
        )

    # ── Pagination ────────────────────────────────────────────────────────────
    total = len(df)
    n_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    pc1, pc2 = st.columns([6, 2])
    with pc2:
        page_num = st.number_input(
            f"Page (of {n_pages})", min_value=1, max_value=n_pages, value=1,
            key=f"_colmap_page_{job_name}",
        )
    start = (page_num - 1) * PAGE_SIZE
    end   = min(start + PAGE_SIZE, total)
    df_page = df.iloc[start:end]

    st.caption(
        f"Showing rows {start+1}–{end} of {total}"
        + (f" (filtered from {len(df_all)})" if total < len(df_all) else "")
    )

    # ── Grid display ──────────────────────────────────────────────────────────
    display_cols = ["Source Component", "Source Table", "Source Column",
                    "Target Table", "Target Column", "Rule"]
    st.dataframe(
        df_page[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Source Component": st.column_config.TextColumn(width="medium"),
            "Source Table":     st.column_config.TextColumn(width="medium"),
            "Source Column":    st.column_config.TextColumn(width="medium"),
            "Target Table":     st.column_config.TextColumn(width="medium"),
            "Target Column":    st.column_config.TextColumn(width="medium"),
            "Rule":             st.column_config.TextColumn(width="small"),
        },
    )

    # Store filtered df for exports
    st.session_state[f"_colmap_filtered_{job_name}"] = df[display_cols]

    # ── Rule summary chips ─────────────────────────────────────────────────────
    _section_label("Rule Breakdown")
    rule_counts = df["Rule"].value_counts()
    chips_html = ""
    color_map = {
        "Direct Mapping": ("#e8f5e9", "#2e7d32"),
        "Expression":     ("#fff8e1", "#e65100"),
        "Join":           ("#f3e5f5", "#6a1b9a"),
    }
    for rule, cnt in rule_counts.items():
        bg, fg = color_map.get(rule, ("#f5f5f5", "#424242"))
        chips_html += _pill(f"{rule}: {cnt}", bg, fg)
    if chips_html:
        st.markdown(f'<div style="margin-bottom:10px;">{chips_html}</div>',
                    unsafe_allow_html=True)

    # ── Expression detail ────────────────────────────────────────────────────
    expr_mappings = [m for m in mappings if m.rule_type == "expression" and m.expression]
    if expr_mappings:
        _section_label(f"📝 Expression Detail ({min(len(expr_mappings), MAX_EXPR_DETAIL)} of {len(expr_mappings)})")
        show_all_expr = False
        if len(expr_mappings) > MAX_EXPR_DETAIL and not show_all_expr:
            show_all_expr = st.toggle(
                f"Show {len(expr_mappings) - MAX_EXPR_DETAIL} more expressions",
                value=False,
                key=f"_colmap_expr_more_{job_name}",
            )
        visible_expr_mappings = expr_mappings if show_all_expr else expr_mappings[:MAX_EXPR_DETAIL]
        for m in visible_expr_mappings:
            src_fields = re.findall(r'\b(\w+)\.(\w+)\b', m.expression)
            src_refs = ", ".join(f"{t}.{c}" for t, c in src_fields[:5]) or "—"
            ico, _, bg, fg = RULE_DISPLAY.get(m.rule, ("📝", m.rule, "#f5f5f5", "#424242"))
            with st.expander(
                f"{ico} {m.target_column}  ← {m.source_component}",
                expanded=False,
            ):
                st.markdown(
                    f'<div class="cm-expr-card">'
                    f'<div class="cm-expr-target">🎯 Target: {_html.escape(m.target_column)}</div>'
                    f'<div style="font-size:11px;color:#8a8a85;margin-bottom:4px;">'
                    f'Rule: {_html.escape(m.rule)}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.code(m.expression, language="java")
                st.markdown(
                    f'<div style="font-size:12px;color:#5a5a56;margin-top:4px;">'
                    f'<strong>Source fields used:</strong> {_html.escape(src_refs)}</div>',
                    unsafe_allow_html=True,
                )
        if len(expr_mappings) > MAX_EXPR_DETAIL and not show_all_expr:
            st.caption(f"… and {len(expr_mappings) - MAX_EXPR_DETAIL} more expressions")


def _render_rule_details_only(rule_details: list[MappingRuleDetail], job_name: str) -> None:
    """Render just rule details when no column mappings are available."""
    if not rule_details:
        return
    _section_label("Mapping Rules")
    for rtype in ("Output", "Lookup", "Reject", "Expression Filter"):
        rows = [rd for rd in rule_details if rd.rule_type == rtype]
        if rows:
            icon = {"Output": "🟢", "Lookup": "🔵", "Reject": "🔴"}.get(rtype, "🟡")
            with st.expander(f"{icon} {rtype} ({len(rows)})", expanded=False):
                st.dataframe(
                    pd.DataFrame([{"Table": r.table, "Join Type": r.join_type,
                                   "Match Mode": r.match_mode,
                                   "Filter": r.filter_expression} for r in rows]),
                    use_container_width=True, hide_index=True,
                )


# ── tMap Drilldown ────────────────────────────────────────────────────────────

def _render_tmap_drilldown(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    _section_label("🗺️ tMap Drilldown")
    st.caption("Expand each tMap component to inspect its input/output tables and mappings.")

    # Group mappings by source component
    groups: dict[str, list[ColumnMapping]] = OrderedDict()
    for m in mappings:
        groups.setdefault(m.source_component, []).append(m)

    tmap_names = list(groups.keys())
    shown = tmap_names[:MAX_TMAP_EXPANDERS]
    extra = len(tmap_names) - len(shown)

    for tmap_name in shown:
        tmap_mappings = groups[tmap_name]
        n_direct = sum(1 for m in tmap_mappings if m.rule_type == "direct")
        n_expr   = sum(1 for m in tmap_mappings if m.rule_type == "expression")
        n_join   = sum(1 for m in tmap_mappings if m.rule_type == "join")
        in_tables  = sorted({m.source_table for m in tmap_mappings if m.source_table})
        out_tables = sorted({m.target_table for m in tmap_mappings if m.target_table})
        tmap_rules = [rd for rd in rule_details
                      if rd.table in out_tables or rd.table in in_tables]
        n_lookup = sum(1 for rd in tmap_rules if rd.rule_type == "Lookup")

        with st.expander(
            f"🗺️ {tmap_name}  —  {len(tmap_mappings)} mapping(s)",
            expanded=False,
        ):
            # KPI badges
            kc1, kc2, kc3, kc4 = st.columns(4)
            kc1.markdown(_kpi_card("Total", len(tmap_mappings), "mappings", "#3C3489"),
                         unsafe_allow_html=True)
            kc2.markdown(_kpi_card("Direct", n_direct, "copy/cast", "#2e7d32"),
                         unsafe_allow_html=True)
            kc3.markdown(_kpi_card("Expression", n_expr, "transforms", "#e65100"),
                         unsafe_allow_html=True)
            kc4.markdown(_kpi_card("Lookup", n_lookup, "rules", "#0369a1"),
                         unsafe_allow_html=True)

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # Input / Output tables
            tc1, tc2 = st.columns(2)
            with tc1:
                st.markdown("**📥 Input Tables**")
                if in_tables:
                    badges = "".join(_pill(t, "#e3f2fd", "#1565c0") for t in in_tables)
                    st.markdown(f'<div>{badges}</div>', unsafe_allow_html=True)
                else:
                    _empty_state("None detected")
            with tc2:
                st.markdown("**📤 Output Tables**")
                if out_tables:
                    badges = "".join(_pill(t, "#e8f5e9", "#2e7d32") for t in out_tables)
                    st.markdown(f'<div>{badges}</div>', unsafe_allow_html=True)
                else:
                    _empty_state("None detected")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            # Mapping detail table
            df_tmap = pd.DataFrame([{
                "Source Table":  m.source_table,
                "Source Column": m.source_column,
                "Target Column": m.target_column,
                "Rule":          RULE_DISPLAY.get(m.rule, ("📝", m.rule, "", ""))[1],
                "Expression":    (m.expression[:70] + "…") if len(m.expression) > 70 else m.expression,
            } for m in tmap_mappings])

            st.dataframe(df_tmap, use_container_width=True, hide_index=True,
                         column_config={
                             "Expression": st.column_config.TextColumn(width="large"),
                         })

            # Lookup rules for this tMap
            lookup_rules = [rd for rd in tmap_rules if rd.rule_type == "Lookup"]
            if lookup_rules:
                st.markdown("**🔵 Lookup Rules**")
                st.dataframe(
                    pd.DataFrame([{
                        "Table": rd.table, "Join Type": rd.join_type,
                        "Match Mode": rd.match_mode, "Filter": rd.filter_expression,
                    } for rd in lookup_rules]),
                    use_container_width=True, hide_index=True,
                )

    if extra > 0:
        st.caption(f"… and {extra} more tMap component(s) not shown (>{MAX_TMAP_EXPANDERS} limit)")


# ── Visual Lineage ────────────────────────────────────────────────────────────

def _render_lineage(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    _section_label("🔄 Visual Lineage")
    st.caption("End-to-end data flow from source tables through tMap transformations to target tables.")

    if len(mappings) > LINEAGE_MAX_MAPPINGS:
        st.warning(
            f"Lineage diagram not rendered — {len(mappings)} mappings exceed the "
            f"{LINEAGE_MAX_MAPPINGS}-mapping display limit. Use filters to narrow scope."
        )
        return

    mermaid_lines = ["graph LR"]

    # Unique source → tMap → target triples
    src_tables  = sorted({m.source_table for m in mappings if m.source_table})
    tmap_names  = sorted({m.source_component for m in mappings})
    tgt_tables  = sorted({m.target_table for m in mappings if m.target_table})
    lookup_tables = sorted({rd.table for rd in rule_details if rd.rule_type == "Lookup"})

    # Nodes
    for t in src_tables:
        mermaid_lines.append(f'    SRC_{_safe_id(t)}[("📥 {t}")]')
    for n in tmap_names:
        n_expr = sum(1 for m in mappings if m.source_component == n and m.rule_type == "expression")
        label  = f"⚙️ {n}\\n{n_expr} expr" if n_expr else f"🗺️ {n}"
        mermaid_lines.append(f'    TMAP_{_safe_id(n)}["{label}"]')
    for t in tgt_tables:
        mermaid_lines.append(f'    TGT_{_safe_id(t)}[("📤 {t}")]')
    for lk in lookup_tables:
        if lk not in src_tables:
            mermaid_lines.append(f'    LKP_{_safe_id(lk)}[("🔵 {lk}")]')

    # Edges: source tables → tMap
    pairs_seen: set[tuple] = set()
    for m in mappings:
        if m.source_table and m.source_component:
            key = (m.source_table, m.source_component)
            if key not in pairs_seen:
                pairs_seen.add(key)
                cnt = sum(1 for x in mappings
                          if x.source_table == m.source_table
                          and x.source_component == m.source_component)
                mermaid_lines.append(
                    f'    SRC_{_safe_id(m.source_table)} -->|"{cnt} cols"| TMAP_{_safe_id(m.source_component)}'
                )

    # Edges: tMap → target tables
    tmap_tgt_seen: set[tuple] = set()
    for m in mappings:
        if m.source_component and m.target_table:
            key = (m.source_component, m.target_table)
            if key not in tmap_tgt_seen:
                tmap_tgt_seen.add(key)
                n_expr_edge = sum(1 for x in mappings
                                  if x.source_component == m.source_component
                                  and x.target_table == m.target_table
                                  and x.rule_type == "expression")
                label = "🔀 expr" if n_expr_edge else "→"
                mermaid_lines.append(
                    f'    TMAP_{_safe_id(m.source_component)} -->|"{label}"| TGT_{_safe_id(m.target_table)}'
                )

    # Lookup edges (dashed)
    lookup_edge_seen: set[tuple[str, str]] = set()
    for rd in rule_details:
        if rd.rule_type == "Lookup" and rd.table:
            for tmap_name in tmap_names:
                edge_key = (rd.table, tmap_name)
                if edge_key in lookup_edge_seen:
                    continue
                lookup_edge_seen.add(edge_key)
                mermaid_lines.append(
                    f'    LKP_{_safe_id(rd.table)} -.->|"lookup"| TMAP_{_safe_id(tmap_name)}'
                )

    if len(mermaid_lines) > 1:
        render_mermaid_diagram("\n".join(mermaid_lines), height=360)
    else:
        _empty_state("No lineage could be determined from available mappings.")

    st.markdown(
        '<div class="cm-lineage-note">Solid arrows = data flow. '
        'Dashed arrows = lookup references.</div>',
        unsafe_allow_html=True,
    )


# ── Impact Analysis ───────────────────────────────────────────────────────────

def _render_impact_analysis(mappings: list[ColumnMapping], job_name: str) -> None:
    _section_label("🎯 Impact Analysis")
    st.caption("Select a target column to trace all source fields and transformations that feed it.")

    target_cols = sorted({m.target_column for m in mappings if m.target_column})
    if not target_cols:
        _empty_state("No target columns found.")
        return

    sel_target = st.selectbox(
        "Select Target Column",
        target_cols,
        key=f"_colmap_impact_{job_name}",
    )

    related = [m for m in mappings if m.target_column == sel_target]

    # KPI
    kc1, kc2, kc3, kc4 = st.columns(4)
    src_fields  = [(m.source_table, m.source_column) for m in related]
    src_tables  = sorted({m.source_table for m in related})
    rule_types  = sorted({RULE_DISPLAY.get(m.rule, ("", m.rule, "", ""))[1] for m in related})
    n_expr      = sum(1 for m in related if m.rule_type == "expression")

    kc1.markdown(_kpi_card("Source Fields",  len(src_fields),  "feeding this column", "#3C3489"), unsafe_allow_html=True)
    kc2.markdown(_kpi_card("Source Tables",  len(src_tables),  "input tables",        "#0369a1"), unsafe_allow_html=True)
    kc3.markdown(_kpi_card("Rule Types",     len(rule_types),  "unique rules",        "#2e7d32"), unsafe_allow_html=True)
    kc4.markdown(_kpi_card("Expressions",    n_expr,           "non-direct mappings", "#e65100"), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Source lineage
    st.markdown(f"**📥 Source lineage for `{sel_target}`**")
    for tbl in src_tables:
        fields = [m.source_column for m in related if m.source_table == tbl]
        badges = "".join(_pill(f, "#e3f2fd", "#1565c0") for f in fields)
        st.markdown(
            f'<div style="margin-bottom:6px;">'
            f'<span style="font-size:12px;font-weight:700;color:#1a1a18;">{_html.escape(tbl)}</span>'
            f'<span style="font-size:11px;color:#8a8a85;"> → </span>'
            f'{badges}</div>',
            unsafe_allow_html=True,
        )

    # Transformation detail
    for m in related:
        ico, lbl, bg, fg = RULE_DISPLAY.get(m.rule, ("📝", m.rule, "#f5f5f5", "#424242"))
        card_html = (
            f'<div class="cm-pitch" style="border-left-color:{fg};background:{bg};">'
            f'<p><strong>{ico} {lbl}</strong> — '
            f'{_html.escape(m.source_component)}: '
            f'{_html.escape(m.source_table)}.{_html.escape(m.source_column)} → '
            f'{_html.escape(m.target_column)}'
        )
        if m.expression:
            card_html += f'<br><code style="font-size:11px;">{_html.escape(m.expression[:120])}</code>'
        card_html += '</p></div>'
        st.markdown(card_html, unsafe_allow_html=True)


# ── Source-Target Matrix ──────────────────────────────────────────────────────

def _render_matrix(mappings: list[ColumnMapping], job_name: str) -> None:
    _section_label("🔢 Source-Target Matrix")
    st.caption("Pivot view: number of column mappings between each source table and target table.")

    src_tables = sorted({m.source_table for m in mappings if m.source_table})
    tgt_tables = sorted({m.target_table for m in mappings if m.target_table})

    if not src_tables or not tgt_tables:
        _empty_state("No source/target tables found.")
        return

    # Build pivot
    data = {}
    for tgt in tgt_tables:
        col_data = {}
        for src in src_tables:
            cnt = sum(1 for m in mappings
                      if m.source_table == src and m.target_table == tgt)
            col_data[src] = cnt
        data[tgt] = col_data

    df_matrix = pd.DataFrame(data, index=src_tables).fillna(0).astype(int)

    # Highlight non-zero
    def _highlight(val):
        if val == 0:
            return "background: #f9fafb; color: #ccc;"
        return "background: #EEEDFE; color: #3C3489; font-weight: 700;"

    st.dataframe(
        df_matrix.style.applymap(_highlight),
        use_container_width=True,
    )

    # Row expansion
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    sel_src = st.selectbox(
        "Expand source table",
        ["— select —"] + src_tables,
        key=f"_colmap_matrix_src_{job_name}",
    )
    if sel_src and sel_src != "— select —":
        detail_rows = []
        for tgt in tgt_tables:
            m_slice = [m for m in mappings
                       if m.source_table == sel_src and m.target_table == tgt]
            if m_slice:
                rules = {RULE_DISPLAY.get(m.rule, ("", m.rule, "", ""))[1] for m in m_slice}
                n_d   = sum(1 for m in m_slice if m.rule_type == "direct")
                n_e   = sum(1 for m in m_slice if m.rule_type == "expression")
                total = len(m_slice)
                detail_rows.append({
                    "Target Table":    tgt,
                    "Mapping Count":   total,
                    "Rule Types":      ", ".join(sorted(rules)),
                    "Direct %":        f"{round(100*n_d/total)}%" if total else "—",
                    "Expression %":    f"{round(100*n_e/total)}%" if total else "—",
                })
        if detail_rows:
            st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)


# ── AI Explanation ────────────────────────────────────────────────────────────

def _render_ai_explanation(mappings: list[ColumnMapping], job_name: str) -> None:
    _section_label("🤖 AI Explanation")
    st.caption("Generate plain-English descriptions of the column mappings and transformations.")

    try:
        from app.ai.llm_engine import ask_ollama
    except ImportError:
        st.info("AI engine (ask_ollama) not available.")
        return

    use_ai = st.checkbox("Use AI (Ollama)", value=False, key=f"_colmap_use_ai_{job_name}")

    # Per-tMap explanation
    tmap_names = sorted({m.source_component for m in mappings})
    if st.button("✨ Explain Mappings", key=f"_colmap_explain_{job_name}"):
        for tmap_name in tmap_names[:5]:
            tmap_mappings = [m for m in mappings if m.source_component == tmap_name]
            src_cols = ", ".join(sorted({m.source_column for m in tmap_mappings})[:10])
            tgt_cols = ", ".join(sorted({m.target_column for m in tmap_mappings})[:10])
            rules    = ", ".join(sorted({m.rule for m in tmap_mappings}))
            prompt = (
                f"You are a business analyst explaining a Talend tMap component.\n"
                f"Component: {tmap_name}\n"
                f"Source columns: {src_cols}\n"
                f"Target columns: {tgt_cols}\n"
                f"Transformation rules: {rules}\n"
                f"Write 2-3 plain-English sentences describing what this mapping does. "
                f"No code. No variable names. Business language only."
            )
            with st.spinner(f"Explaining {tmap_name}…"):
                result = ask_ollama(prompt, use_ollama=use_ai)
            st.session_state[f"_colmap_ai_{job_name}_{tmap_name}"] = result

        # Expression summary
        expr_mappings = [m for m in mappings if m.rule_type == "expression"]
        if expr_mappings:
            expr_list = "\n".join(
                f"- {m.target_column}: {m.expression[:80]}"
                for m in expr_mappings[:20]
            )
            expr_prompt = (
                f"Summarise these {len(expr_mappings)} expression-based data transformations "
                f"in 2 plain-English sentences. No code.\n{expr_list}"
            )
            with st.spinner("Summarising expressions…"):
                st.session_state[f"_colmap_ai_expr_{job_name}"] = ask_ollama(
                    expr_prompt, use_ollama=use_ai
                )

        # Business summary
        n_tmaps = len(tmap_names)
        biz_prompt = (
            f"You are a business analyst. Explain what data transformation this job does "
            f"based on {len(mappings)} column mappings across {n_tmaps} tMap component(s). "
            f"Source tables: {', '.join(sorted({m.source_table for m in mappings})[:6])}. "
            f"Target tables: {', '.join(sorted({m.target_table for m in mappings})[:6])}. "
            f"Use plain business language. No code. Under 100 words."
        )
        with st.spinner("Writing business summary…"):
            st.session_state[f"_colmap_ai_biz_{job_name}"] = ask_ollama(
                biz_prompt, use_ollama=use_ai
            )

    # Render stored AI results
    for tmap_name in tmap_names[:5]:
        ai_text = st.session_state.get(f"_colmap_ai_{tmap_name}_{job_name}") or \
                  st.session_state.get(f"_colmap_ai_{job_name}_{tmap_name}")
        if ai_text:
            st.markdown(
                f'<div class="cm-pitch" style="border-left-color:#3C3489;">'
                f'<p>🧠 <strong>{_html.escape(tmap_name)}</strong><br>{_html.escape(ai_text)}</p></div>',
                unsafe_allow_html=True,
            )

    expr_summary = st.session_state.get(f"_colmap_ai_expr_{job_name}")
    if expr_summary:
        st.markdown(
            f'<div class="cm-pitch" style="border-left-color:#e65100;">'
            f'<p>🔀 <strong>Expression Summary</strong><br>{_html.escape(expr_summary)}</p></div>',
            unsafe_allow_html=True,
        )

    biz_summary = st.session_state.get(f"_colmap_ai_biz_{job_name}")
    if biz_summary:
        st.markdown("**📋 Business Summary of Column Mappings**")
        st.markdown(
            f'<div class="cm-pitch"><p>{_html.escape(biz_summary)}</p></div>',
            unsafe_allow_html=True,
        )
        copy_text = json.dumps(str(biz_summary))
        components_html(
            f"""
            <button
              style="border:1px solid #d8d6cc;background:#fff;color:#3C3489;
                     border-radius:6px;padding:6px 10px;font-size:12px;
                     font-weight:700;cursor:pointer;"
              onclick='navigator.clipboard.writeText({copy_text})'>
              Copy to clipboard
            </button>
            """,
            height=38,
        )


# ── Exports ───────────────────────────────────────────────────────────────────

def _render_exports(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str,
) -> None:
    _section_label("📤 Export")

    df_filtered = st.session_state.get(
        f"_colmap_filtered_{job_name}",
        _build_df(mappings)[["Source Component", "Source Table", "Source Column",
                              "Target Table", "Target Column", "Rule"]],
    )

    total_all      = len(mappings)
    total_filtered = len(df_filtered)
    st.caption(
        f"Exporting {total_filtered} of {total_all} mappings"
        + (" (current filters applied)" if total_filtered < total_all else "")
    )

    no_data = total_filtered == 0
    if no_data:
        st.warning("No mappings to export. Adjust your filters.")

    ec1, ec2, ec3 = st.columns(3)

    # CSV
    with ec1:
        st.download_button(
            "📥 Export CSV",
            data=df_filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"{job_name}_column_mappings.csv",
            mime="text/csv",
            key=f"_colmap_csv_{job_name}",
            disabled=no_data,
            use_container_width=True,
        )

    # Excel
    with ec2:
        try:
            import openpyxl  # noqa: F401
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_filtered.to_excel(writer, sheet_name="Column Mappings", index=False)

                # Rule summary sheet
                rule_counts = df_filtered["Rule"].value_counts().reset_index()
                rule_counts.columns = ["Rule Type", "Count"]
                rule_counts.to_excel(writer, sheet_name="Rule Summary", index=False)

            buf.seek(0)
            st.download_button(
                "📊 Export Excel",
                data=buf.read(),
                file_name=f"{job_name}_column_mappings.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"_colmap_xlsx_{job_name}",
                disabled=no_data,
                use_container_width=True,
            )
        except ImportError:
            st.info("Excel export requires openpyxl: `pip install openpyxl`")

    # PDF
    with ec3:
        direct_rows   = [m for m in mappings if m.rule_type == "direct"]
        expr_rows     = [m for m in mappings if m.rule_type == "expression" and m.expression]
        pdf_sections  = [
            ("Column Mappings Summary",
             f"{len(mappings)} mappings across "
             f"{len({m.source_component for m in mappings})} tMap component(s).\n"
             f"Direct: {len(direct_rows)}  |  Expression: {len(expr_rows)}  |  "
             f"Join: {sum(1 for m in mappings if m.rule_type == 'join')}"),
            ("Direct Mappings",
             "\n".join(f"{m.source_column} → {m.target_column}"
                       for m in direct_rows[:30]) or "None"),
            ("Expression Mappings",
             "\n".join(f"{m.target_column}: {m.expression[:100]}"
                       for m in expr_rows[:20]) or "None"),
        ]
        if pdf_sections and not no_data:
            pdf_download_button(
                f"Column Mappings — {job_name}",
                pdf_sections,
                key=f"_colmap_pdf_{job_name}",
                file_name=f"{job_name}_column_mappings.pdf",
            )
        else:
            st.button("📄 Export PDF", disabled=True,
                      key=f"_colmap_pdf_dis_{job_name}", use_container_width=True)
