"""Global search over cached repository analysis metadata."""

from __future__ import annotations

import hashlib
import re

import streamlit as st

from app.parser.source_target_extractor import build_source_target_inventory, extract_sql_operations
from app.ui.design_system_v2 import empty_state_card, page_header

_FILTER_OPTIONS = [
    "All",
    "Jobs",
    "Components",
    "Source Tables",
    "Target Tables",
    "Source Columns",
    "Target Columns",
    "SQL",
    "Java",
    "Variables",
    "Mappings",
]

_FILTER_TO_CATEGORIES = {
    "All": None,
    "Jobs": {"Job"},
    "Components": {"Component"},
    "Source Tables": {"Source Table"},
    "Target Tables": {"Target Table"},
    "Source Columns": {"Source Column"},
    "Target Columns": {"Target Column"},
    "SQL": {"SQL"},
    "Java": {"Java"},
    "Variables": {"Variable"},
    "Mappings": {"Mapping"},
}

_CATEGORY_ORDER = [
    "Job",
    "Component",
    "Source Table",
    "Target Table",
    "Source Column",
    "Target Column",
    "SQL",
    "Java",
    "Variable",
    "Mapping",
]

_CATEGORY_COLORS = {
    "Job": ("#EEEDFE", "#3C3489"),
    "Component": ("#E1F5EE", "#085041"),
    "Source Table": ("#E6F1FB", "#0C447C"),
    "Target Table": ("#E6F1FB", "#0C447C"),
    "Source Column": ("#EAF3DE", "#27500A"),
    "Target Column": ("#EAF3DE", "#27500A"),
    "SQL": ("#FAEEDA", "#854F0B"),
    "Java": ("#FAECE7", "#712B13"),
    "Variable": ("#FBEAF0", "#72243E"),
    "Mapping": ("#F1EFE8", "#5F5E5A"),
}

_CATEGORY_TO_JOB360 = {
    "Job": "Overview",
    "Component": "Architecture",
    "Source Table": "Architecture",
    "Target Table": "Architecture",
    "Source Column": "Mapping & Lineage",
    "Target Column": "Mapping & Lineage",
    "SQL": "Technical Analysis",
    "Java": "Technical Analysis",
    "Variable": "Technical Analysis",
    "Mapping": "Mapping & Lineage",
}


def render_repository_search_page() -> None:
    page_header(
        "🔎",
        "Global Search",
        "Search cached jobs, components, tables, columns, SQL, Java, variables, and mappings",
    )

    all_jobs: list[dict] = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        clicked = empty_state_card(
            "No repository loaded",
            "Run an analysis first. Search uses the existing parsed metadata only.",
            status="warning",
            icon="🔎",
            button_label="Go to Home",
            button_key="search_goto_home",
        )
        if clicked:
            st.session_state["_nav_idx2"] = 0
            st.rerun()
        return

    index = _get_index(all_jobs)
    query = st.text_input(
        "search_query",
        placeholder="Search jobs, components, tables, columns, SQL, Java, variables, mappings...",
        label_visibility="collapsed",
        key="repo_search_query",
    )

    active_filter = st.radio(
        "Filter",
        _FILTER_OPTIONS,
        horizontal=True,
        key="repo_search_filter",
    )

    st.caption(f"Index: {len(index):,} records across {len(all_jobs):,} job(s)")
    if not query or len(query.strip()) < 2:
        st.info("Type at least 2 characters to search.")
        return

    q_lower = query.strip().lower()
    allowed = _FILTER_TO_CATEGORIES.get(active_filter)
    results = [
        rec for rec in index
        if (not allowed or rec["category"] in allowed) and q_lower in rec["_search"]
    ]

    if not results:
        st.warning(f"No results for **{query}**.")
        return

    grouped: dict[str, list[dict]] = {}
    for rec in results:
        grouped.setdefault(rec["category"], []).append(rec)

    st.markdown(f"**{len(results):,}** result(s) for _{html_safe(query)}_")
    for category in _CATEGORY_ORDER:
        recs = grouped.get(category, [])
        if not recs:
            continue
        with st.expander(f"{category}s ({len(recs)})", expanded=True):
            for row_idx, rec in enumerate(recs[:50]):
                _render_result_row(rec, q_lower, row_idx)
            if len(recs) > 50:
                st.caption(f"Showing 50 of {len(recs)} results. Refine search to narrow.")


def _get_index(all_jobs: list[dict]) -> list[dict]:
    names = "|".join(j.get("job_data", {}).get("job_name", "") for j in all_jobs)
    fp = hashlib.sha1(f"{len(all_jobs)}:{names}".encode("utf-8")).hexdigest()
    if st.session_state.get("_global_search_index_fp") != fp:
        st.session_state["_global_search_index"] = _build_search_index(all_jobs)
        st.session_state["_global_search_index_fp"] = fp
    return st.session_state["_global_search_index"]


def _build_search_index(all_jobs: list[dict]) -> list[dict]:
    records: list[dict] = []
    for job_entry in all_jobs:
        jd = job_entry.get("job_data", {})
        job_name = jd.get("job_name", "Unknown")
        job_ver = jd.get("job_version", "")
        components = jd.get("components", [])
        inv = job_entry.get("_inv") or build_source_target_inventory(jd)
        sql_ops = inv.get("sql_operations") or extract_sql_operations(components)

        _add(records, "Job", job_name, job_name, f"Version {job_ver}" if job_ver else "Talend job", "Overview")

        seen_components: set[str] = set()
        seen_variables: set[str] = set()
        for comp in components:
            if not isinstance(comp, dict):
                continue
            ctype = comp.get("component_type", "")
            cname = comp.get("unique_name", "")
            params = comp.get("parameters", {}) or {}

            if ctype and ctype not in seen_components:
                seen_components.add(ctype)
                _add(records, "Component", job_name, ctype, f"{cname or ctype} in {job_name}", "Architecture", f"{cname} {params}")

            if ctype in {"tJava", "tJavaRow", "tJavaFlex"}:
                java_text = " ".join(str(v) for v in params.values() if v)
                if java_text:
                    _add(records, "Java", job_name, cname or ctype, java_text[:180], "Technical Analysis", java_text)

            for key, value in params.items():
                text = str(value)
                for var_name in re.findall(r"\b(?:context|globalMap)\.([A-Za-z_][A-Za-z0-9_]*)\b", text):
                    if var_name not in seen_variables:
                        seen_variables.add(var_name)
                        _add(records, "Variable", job_name, var_name, f"Referenced by {cname or ctype}", "Technical Analysis", text)

                if ctype == "tMap" and value and any(token in key.upper() for token in ("EXPR", "EXPRESSION", "MAPPING", "COLUMN", "SCHEMA")):
                    _add(records, "Mapping", job_name, f"{cname or ctype}: {key}", text[:180], "Mapping & Lineage", text)

        for ctx in jd.get("contexts", []):
            ctx_name = ctx.get("name", "") if isinstance(ctx, dict) else str(ctx)
            if ctx_name:
                _add(records, "Variable", job_name, ctx_name, f"Context variable in {job_name}", "Technical Analysis")

        for src in inv.get("sources", []):
            table = src.get("qualified_name") or src.get("name", "")
            if table:
                _add(records, "Source Table", job_name, table, src.get("component", "Source"), "Architecture")
                for col in _columns_from_item(src):
                    _add(records, "Source Column", job_name, col, table, "Mapping & Lineage", table)

        for tgt in inv.get("targets", []):
            table = tgt.get("qualified_name") or tgt.get("name", "")
            if table:
                _add(records, "Target Table", job_name, table, tgt.get("component", "Target"), "Architecture")
                for col in _columns_from_item(tgt):
                    _add(records, "Target Column", job_name, col, table, "Mapping & Lineage", table)

        for sql_op in sql_ops:
            query = sql_op.get("query", "")
            if query:
                snippet = query.replace("\n", " ").strip()
                _add(records, "SQL", job_name, snippet[:90], f"SQL in {job_name}", "Technical Analysis", query)

    return _dedupe(records)


def _add(records: list[dict], category: str, job: str, name: str, description: str, section: str, search_extra: str = "") -> None:
    records.append({
        "name": str(name or "Unnamed"),
        "type": category,
        "category": category,
        "job": job,
        "description": str(description or ""),
        "section": section,
        "_search": f"{name} {description} {job} {search_extra}".lower(),
    })


def _dedupe(records: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for rec in records:
        key = (rec["category"], rec["job"], rec["name"], rec["description"])
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def _columns_from_item(item: dict) -> list[str]:
    columns = []
    for key in ("columns", "schema", "fields"):
        value = item.get(key)
        if isinstance(value, list):
            for col in value:
                if isinstance(col, dict):
                    name = col.get("name") or col.get("column") or col.get("label")
                else:
                    name = str(col)
                if name:
                    columns.append(name)
    return sorted(set(columns))


def _render_result_row(rec: dict, q_lower: str, row_idx: int) -> None:
    col_badge, col_name, col_job, col_action = st.columns([1.2, 3, 2.5, 1.3])
    with col_badge:
        st.markdown(_badge(rec["type"], rec["category"]), unsafe_allow_html=True)
    with col_name:
        st.markdown(_highlight(rec["name"], q_lower), unsafe_allow_html=True)
        st.caption(rec.get("description", ""))
    with col_job:
        st.markdown(f"<span style='font-size:12px;color:#5f5e5a;'>Job: {html_safe(rec['job'])}</span>", unsafe_allow_html=True)
    with col_action:
        key = f"global_search_open_{rec['category']}_{row_idx}_{hashlib.sha1(str(rec).encode('utf-8')).hexdigest()[:10]}"
        if st.button("Open", key=key, use_container_width=True):
            _open_job(rec["job"], rec.get("section") or _CATEGORY_TO_JOB360.get(rec["category"], "Overview"))


def _open_job(job_name: str, category: str = "Overview") -> None:
    st.session_state["_job360_open_job"] = job_name
    st.session_state["_job360_open_category"] = category
    st.session_state["_advanced_page"] = None
    from app.ui.design_system_v2 import _NAV_PAGES
    st.session_state["_nav_idx2"] = next((i for i, (k, _) in enumerate(_NAV_PAGES) if k == "job_analysis"), 4)
    st.rerun()


def _badge(label: str, category: str) -> str:
    bg, fg = _CATEGORY_COLORS.get(category, ("#F1EFE8", "#444441"))
    return (
        f"<span style='background:{bg};color:{fg};font-size:11px;font-weight:600;"
        f"padding:2px 9px;border-radius:999px;white-space:nowrap;'>{html_safe(label)}</span>"
    )


def _highlight(text: str, q_lower: str) -> str:
    text = str(text)
    idx = text.lower().find(q_lower)
    if idx < 0:
        return f"<span style='font-size:13px;font-weight:500;'>{html_safe(text)}</span>"
    return (
        "<span style='font-size:13px;font-weight:500;'>"
        f"{html_safe(text[:idx])}<mark style='background:#FAC775;padding:0 2px;border-radius:2px;'>"
        f"{html_safe(text[idx:idx + len(q_lower)])}</mark>{html_safe(text[idx + len(q_lower):])}</span>"
    )


def html_safe(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
