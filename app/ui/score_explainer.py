"""Score explainer — per-job migration score breakdown using Job 360 style cards."""
from __future__ import annotations
import streamlit as st

from app.ui.design_system_v2 import render_clickable_kpi_row


# ── Colour helpers ────────────────────────────────────────────────────────────

_COMPLEXITY_COLOR = {
    "LOW":      "#15803d",
    "MEDIUM":   "#b45309",
    "HIGH":     "#be123c",
    "CRITICAL": "#7f1d1d",
}

_RAG_COLOR = {
    "GREEN": "#15803d",
    "AMBER": "#b45309",
    "RED":   "#be123c",
}


def _complexity_color(level: str) -> str:
    return _COMPLEXITY_COLOR.get(str(level).upper(), "#475569")


def _rag_color(rag: str) -> str:
    return _RAG_COLOR.get(str(rag).upper(), "#475569")


def _cloud_rag(cr: dict) -> tuple[str, str]:
    """Return (display_label, rag_key) from a cloud_readiness dict."""
    readiness = cr.get("readiness", "")
    mapping = {"HIGH": ("Ready", "GREEN"), "MEDIUM": ("Partial", "AMBER"), "LOW": ("Blocked", "RED")}
    if readiness in mapping:
        return mapping[readiness]
    rag = cr.get("rag", "")
    if rag in _RAG_COLOR:
        return rag, rag
    return "—", "AMBER"


# ── Main render function ──────────────────────────────────────────────────────

def render_score_explainer(job: dict, key_suffix: str = "") -> None:
    """Render a per-job migration score breakdown using the Job 360 card style.

    `key_suffix` lets callers disambiguate widget keys when multiple jobs in
    the same render pass share an identical job_name (e.g. different item
    versions of the same Talend job), which would otherwise collide on the
    `key_prefix=f"se_{job_name}"` used below.
    """
    job_data   = job.get("job_data") or {}
    estimation = job.get("estimation") or {}
    complexity = job.get("complexity") or {}

    level      = (
        complexity.get("complexity")
        or complexity.get("level")
        or estimation.get("complexity")
        or "—"
    )
    cx_score   = complexity.get("score", "—")
    est_hours  = estimation.get("estimated_hours", "—")
    components = job_data.get("components", [])

    cloud_rdy         = job.get("cloud_readiness") or {}
    cloud_label, cloud_rag = _cloud_rag(cloud_rdy)

    risks = [
        r for r in job.get("enterprise_risk_report", [])
        if r.get("risk") in ("HIGH", "CRITICAL")
    ]
    risk_count  = len(risks)
    risk_color  = "#be123c" if risk_count else "#15803d"
    risk_caption = "Needs attention" if risk_count else "All clear"

    cx_color = _complexity_color(str(level))

    # ── KPI row — same render_clickable_kpi_row used by Job 360 ──────────────
    render_clickable_kpi_row(
        [
            {
                "label":   "Complexity",
                "value":   str(level),
                "caption": f"Score: {cx_score}",
                "color":   cx_color,
                "filter":  "Complexity",
            },
            {
                "label":   "Est. Hours",
                "value":   str(est_hours),
                "caption": "Migration effort",
                "color":   "#6d28d9",
                "filter":  "Est. Hours",
            },
            {
                "label":   "Components",
                "value":   str(len(components)),
                "caption": "In this job",
                "color":   "#0369a1",
                "filter":  "Components",
            },
            {
                "label":   "Cloud Readiness",
                "value":   cloud_label,
                "caption": cloud_rag,
                "color":   _rag_color(cloud_rag),
                "filter":  "Cloud Readiness",
            },
            {
                "label":   "High/Critical Risks",
                "value":   str(risk_count),
                "caption": risk_caption,
                "color":   risk_color,
                "filter":  "Risks",
            },
        ],
        state_key=f"score_explainer_{job_data.get('job_name', 'unknown')}{key_suffix}",
        key_prefix=f"se_{job_data.get('job_name', 'unknown')}{key_suffix}",
    )

    # ── Risk detail cards ─────────────────────────────────────────────────────
    if risks:
        with st.expander(f"Risk details ({risk_count})", expanded=False):
            for r in risks:
                sev   = r.get("risk", "HIGH")
                color = "#be123c" if sev == "CRITICAL" else "#b45309"
                st.markdown(
                    f'<div style="border-left:3px solid {color};padding:4px 8px;'
                    f'margin-bottom:4px;font-size:12px;">'
                    f'<b style="color:{color}">{sev}</b> · {r.get("component", "?")} — '
                    f'{r.get("message", "No details")}</div>',
                    unsafe_allow_html=True,
                )

    # ── Migration blocker caption ─────────────────────────────────────────────
    blockers = [
        c for c in components
        if "tJava" in c.get("component_type", "") or "tSystem" in c.get("component_type", "")
    ]
    if blockers:
        st.caption(
            f"⚠️ {len(blockers)} migration blocker component(s): "
            + ", ".join(sorted(set(c["component_type"] for c in blockers[:5])))
        )
