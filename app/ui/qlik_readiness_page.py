from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from app.ui.design_system_v2 import (
    empty_state_card,
    page_header,
    render_clickable_kpi_row,
    styled_dataframe,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_RAG_COLOR = {
    "GREEN": "#15803d",
    "AMBER": "#b45309",
    "RED":   "#be123c",
}

_PATH_LABEL = {
    "QLIK_NATIVE":    "🟢 QLIK_NATIVE",
    "QLIK_PARTIAL":   "🟡 QLIK_PARTIAL",
    "MANUAL_REWRITE": "🔴 MANUAL_REWRITE",
}


def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color}22;color:{color};'
        f'border:1px solid {color}55;border-radius:4px;'
        f'padding:2px 7px;font-size:11px;font-weight:700;">{text}</span>'
    )


def _component_list(items: list[str], color: str) -> None:
    if not items:
        st.caption("_(none)_")
        return
    for ct in items:
        st.markdown(
            f'<div style="font-size:12px;color:{color};'
            f'background:{color}11;border-radius:4px;'
            f'padding:2px 8px;margin-bottom:2px;">{ct}</div>',
            unsafe_allow_html=True,
        )


# ── Main render function ───────────────────────────────────────────────────────

def render_qlik_readiness_page() -> None:
    page_header(
        "🔵",
        "Talend Migration Readiness",
        "Native · Partial · Rewrite classification per job",
    )

    all_jobs: list[dict] = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        empty_state_card(
            "No repository loaded",
            "Upload and analyse a Talend ZIP on the Home page first.",
            "warning",
        )
        return

    from app.analyzers.qlik_readiness_analyzer import analyze_qlik_readiness

    results: list[dict] = analyze_qlik_readiness(all_jobs)
    st.session_state["qlik_readiness"] = results

    if not results:
        empty_state_card("No results", "Qlik analysis returned no data.", "warning")
        return

    # ── Counts ────────────────────────────────────────────────────────────────
    total = len(results)
    native_count  = sum(1 for r in results if r["qlik_path"] == "QLIK_NATIVE")
    partial_count = sum(1 for r in results if r["qlik_path"] == "QLIK_PARTIAL")
    manual_count  = sum(1 for r in results if r["qlik_path"] == "MANUAL_REWRITE")
    weeks_saved   = round(native_count * 3.5)

    # ── Row 1: KPI cards — Job 360 style ─────────────────────────────────────
    render_clickable_kpi_row(
        [
            {"label": "Talend Native",    "value": str(native_count),  "caption": "Direct lift (GREEN)",          "color": "#15803d", "filter": "QLIK_NATIVE"},
            {"label": "Talend Partial",   "value": str(partial_count), "caption": "Hybrid approach (AMBER)",      "color": "#b45309", "filter": "QLIK_PARTIAL"},
            {"label": "Manual Rewrite",   "value": str(manual_count),  "caption": "Full rewrite (RED)",           "color": "#be123c", "filter": "MANUAL_REWRITE"},
            {"label": "Est. Weeks Saved", "value": str(weeks_saved),   "caption": "vs full manual migration",     "color": "#6d28d9", "filter": "Savings"},
        ],
        state_key="talend_readiness_filter",
        key_prefix="tr_kpi",
    )

    # ── Row 2: Summary caption ────────────────────────────────────────────────
    st.caption(
        f"{native_count} of {total} jobs can migrate natively. "
        f"Est. savings vs manual: {weeks_saved} weeks."
    )

    # ── Row 3: DataFrame ──────────────────────────────────────────────────────
    st.markdown(
        "**Legend:** "
        + _badge("QLIK_NATIVE", "#15803d")
        + " &nbsp;"
        + _badge("QLIK_PARTIAL", "#b45309")
        + " &nbsp;"
        + _badge("MANUAL_REWRITE", "#be123c"),
        unsafe_allow_html=True,
    )

    rows = []
    for r in results:
        job_data = next(
            (j["job_data"] for j in all_jobs if j["job_data"].get("job_name") == r["job_name"]),
            {},
        )
        component_count = len(job_data.get("components", []))
        rows.append({
            "Job":             r["job_name"],
            "Components":      component_count,
            "Qlik Path":       _PATH_LABEL.get(r["qlik_path"], r["qlik_path"]),
            "Migration Tool":  r["migration_tool"],
            "Recommendation":  r["recommendation"],
            "Score":           r["qlik_score"],
        })

    df = pd.DataFrame(rows)
    styled_dataframe(df, "qlik_readiness_table", hide_index=True)

    # ── Row 4: Per-job expanders ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown("**Per-job component breakdown**")
    for r in results:
        rag_color = _RAG_COLOR.get(r["qlik_rag"], "#64748b")
        with st.expander(
            f"{r['job_name']} — {r['qlik_path']}",
            expanded=False,
        ):
            col_native, col_blocker = st.columns(2)
            with col_native:
                st.markdown(
                    f'<div style="font-size:12px;font-weight:700;color:{_RAG_COLOR["GREEN"]};margin-bottom:4px;">'
                    f"✅ Native-friendly components</div>",
                    unsafe_allow_html=True,
                )
                _component_list(r.get("native_components", []), _RAG_COLOR["GREEN"])
            with col_blocker:
                st.markdown(
                    f'<div style="font-size:12px;font-weight:700;color:{_RAG_COLOR["RED"]};margin-bottom:4px;">'
                    f"🚫 Blocker components</div>",
                    unsafe_allow_html=True,
                )
                _component_list(r.get("blocker_components", []), _RAG_COLOR["RED"])
            st.markdown(
                f'<div style="margin-top:6px;font-size:12px;color:#475569;">'
                f'<b>Score:</b> {r["qlik_score"]}/100 &nbsp;|&nbsp; '
                f'<b>Tool:</b> {r["migration_tool"]} &nbsp;|&nbsp; '
                f'{r["recommendation"]}</div>',
                unsafe_allow_html=True,
            )

    # ── Download ──────────────────────────────────────────────────────────────
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Talend Readiness CSV",
        data=csv_bytes,
        file_name="talend_readiness.csv",
        mime="text/csv",
        use_container_width=True,
    )
