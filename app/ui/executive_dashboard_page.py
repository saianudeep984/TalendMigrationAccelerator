"""
Executive Dashboard page.

Binds session-state repository analysis data to the ExecutiveDashboard model
(app.analyzers.models.ExecutiveDashboard) and renders:
  1. An auto-generated Executive Summary card (Repository Health, Migration
     Coverage, Major Blockers, Strengths, Estimated Migration Effort,
     Highest Priority Action) — pure template formatting over already
     computed metrics, no AI / LLM call involved.
  2. Top summary — Repository Health Score, Overall Status, Migration
     Coverage, Top Issues, Estimated Effort (single source of truth: the
     same get_health_score() result used everywhere else in the app).
  3. Score Breakdown (Name · Progress bar · Score · Short description) and
     Top Issues (Issue · Severity · Impact · Recommendation), side by side.
  4. The full detail view (clickable KPI strip, charts, drilldowns, report
     pack) provided by app.ui.dashboard.render_executive_dashboard.
  5. A single bottom banner showing Overall Status only.

No scoring/business logic is computed in this module — every number shown
here comes from app.analyzers.health_score.get_health_score() or the
ExecutiveDashboard model, both already computed elsewhere in the app.

Registered route key: "executive_dashboard"
Registered nav entry:  ("executive_dashboard", "Executive Dashboard") in
                        app.ui.design_system_v2._NAV_PAGES
"""
import html as _html

import streamlit as st

from app.analyzers.models import ExecutiveDashboard
from app.ui.design_system_v2 import empty_state_card, render_rag_banner, styled_dataframe

# ── Presentation-only copy: maps a health-score dimension key to the
# Impact / Recommendation text shown in the Top Issues table. This is
# display copy only — it does not change any score, threshold, or weight
# computed in app.analyzers.health_score. ─────────────────────────────────
_DIMENSION_GUIDANCE: dict[str, dict[str, str]] = {
    "migration_readiness": {
        "impact": "Jobs may not be portable to the target platform without rework.",
        "recommendation": "Review the Migration Readiness Score breakdown and resolve flagged components first.",
    },
    "complexity": {
        "impact": "Complex jobs take longer to migrate and are more likely to need manual rework.",
        "recommendation": "Prioritise simplification or re-design of the highest-complexity jobs before migration.",
    },
    "sql_risk": {
        "impact": "Embedded SQL logic may behave differently or be unsupported on the target platform.",
        "recommendation": "Review SQL transformations and rewrite high-risk queries for the target platform.",
    },
    "java_risk": {
        "impact": "Custom Java code can block automated migration and requires manual conversion.",
        "recommendation": "Review flagged Java routines for version compatibility and plan manual conversion effort.",
    },
    "documentation": {
        "impact": "Missing documentation slows down validation and increases migration risk.",
        "recommendation": "Backfill job and routine documentation before migration sign-off.",
    },
    "deprecated": {
        "impact": "Deprecated components may be unsupported or removed on the target platform.",
        "recommendation": "Replace deprecated components with their supported equivalents.",
    },
    "error_count": {
        "impact": "Unresolved HIGH/CRITICAL findings indicate jobs that are not migration-ready.",
        "recommendation": "Resolve HIGH/CRITICAL risk findings before scheduling these jobs for migration.",
    },
}


# ── Presentation-only copy: a few dimension labels read better when framed
# as a strength than as a "risk" (e.g. "Java Risk" scoring well is better
# described as "Java Quality"). Display text only — same key/score as
# everywhere else, no new computation. ───────────────────────────────────
_STRENGTH_LABEL_OVERRIDES: dict[str, str] = {
    "java_risk": "Java Quality",
    "sql_risk": "SQL Quality",
    "error_count": "Error Resolution",
    "deprecated": "Component Currency",
}


def _build_executive_summary(model: "ExecutiveDashboard", hs_result: dict) -> dict:
    """Deterministically assemble the Executive Summary card's text from
    metrics already computed elsewhere — get_health_score() for the score /
    status / per-dimension scores, ExecutiveDashboard for coverage and
    effort. No AI / LLM call, no new scoring: this only selects, sorts, and
    formats numbers and labels that already exist.
    """
    overall_score = hs_result.get("overall_score", hs_result.get("health_score", 0))
    overall_status = hs_result.get("overall_status", hs_result.get("risk_level", "RED"))
    dims = hs_result.get("metric_scores", hs_result.get("dimensions", []))

    total_jobs = model.total_jobs or 0
    analyzed_jobs = model.analyzed_jobs or 0
    coverage_pct = int(round((analyzed_jobs / total_jobs) * 100)) if total_jobs else 0

    est_days = model.estimated_days if model.estimated_days not in (None, "") else "—"

    sorted_dims = sorted(dims, key=lambda d: d["score"])

    # Blockers — lowest-scoring dimensions that are not yet healthy
    # (score < 80, same threshold already used for AMBER/RED elsewhere).
    blockers = [d["label"] for d in sorted_dims if d["score"] < 80][:2]

    # Strengths — highest-scoring dimensions (score >= 80), shown with
    # the friendlier display label where one exists.
    strengths_pool = [d for d in sorted_dims if d["score"] >= 80]
    strengths_pool.sort(key=lambda d: d["score"], reverse=True)
    strengths = [
        _STRENGTH_LABEL_OVERRIDES.get(d["key"], d["label"]) for d in strengths_pool
    ][:2]

    # Highest priority action — the recommendation already written for the
    # single worst-scoring dimension (same copy used in the Top Issues table).
    priority_action = "No action required — all dimensions are healthy."
    if sorted_dims and sorted_dims[0]["score"] < 80:
        worst = sorted_dims[0]
        guidance = _DIMENSION_GUIDANCE.get(worst["key"], {})
        priority_action = guidance.get(
            "recommendation", f"Review {worst['label']} before proceeding with migration."
        )

    return {
        "overall_score": overall_score,
        "overall_status": overall_status,
        "coverage_pct": coverage_pct,
        "blockers": blockers,
        "strengths": strengths,
        "estimated_days": est_days,
        "priority_action": priority_action,
    }


def _render_executive_summary_card(model: "ExecutiveDashboard", hs_result: dict) -> None:
    """Renders the auto-generated Executive Summary card. Pure template
    formatting over _build_executive_summary() — no AI, no new analysis."""
    summary = _build_executive_summary(model, hs_result)

    status = summary["overall_status"]
    status_color = {"GREEN": "#15803d", "AMBER": "#b45309", "RED": "#be123c"}.get(status, "#64748b")
    status_label = status.title() if status else "—"

    def _bullet_list(items: list[str], empty_text: str) -> str:
        if not items:
            return f'<div style="font-size:12px;color:#94a3b8;">{_html.escape(empty_text)}</div>'
        return "".join(
            f'<div style="font-size:13px;color:#0f172a;padding:3px 0;">• {_html.escape(i)}</div>'
            for i in items
        )

    st.markdown(
        f"""
        <div style="background:#fff;border:1px solid #dbe3ef;border-radius:12px;
        padding:18px 20px;margin-bottom:14px;box-shadow:0 1px 2px rgba(15,23,42,.05);">
          <div style="font-size:13px;font-weight:800;color:#64748b;text-transform:uppercase;
          letter-spacing:.06em;margin-bottom:12px;">📝 Executive Summary</div>

          <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px;">
            <div>
              <div style="font-size:11px;color:#64748b;font-weight:600;">Repository Health</div>
              <div style="font-size:18px;font-weight:800;color:{status_color};">
                {summary['overall_score']}/100 ({status_label})
              </div>
            </div>
            <div>
              <div style="font-size:11px;color:#64748b;font-weight:600;">Migration Coverage</div>
              <div style="font-size:18px;font-weight:800;color:#0369a1;">{summary['coverage_pct']}%</div>
            </div>
            <div>
              <div style="font-size:11px;color:#64748b;font-weight:600;">Estimated Migration Effort</div>
              <div style="font-size:18px;font-weight:800;color:#6d28d9;">{summary['estimated_days']} Days</div>
            </div>
          </div>

          <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:14px;">
            <div style="flex:1;min-width:200px;">
              <div style="font-size:11px;color:#be123c;font-weight:700;text-transform:uppercase;
              letter-spacing:.04em;margin-bottom:4px;">Major Blockers</div>
              {_bullet_list(summary['blockers'], "None — no major blockers found.")}
            </div>
            <div style="flex:1;min-width:200px;">
              <div style="font-size:11px;color:#15803d;font-weight:700;text-transform:uppercase;
              letter-spacing:.04em;margin-bottom:4px;">Strengths</div>
              {_bullet_list(summary['strengths'], "No dimensions currently score in the healthy range.")}
            </div>
          </div>

          <div style="border-top:1px solid #e2e8f0;padding-top:12px;">
            <div style="font-size:11px;color:#64748b;font-weight:700;text-transform:uppercase;
            letter-spacing:.04em;margin-bottom:3px;">Highest Priority Action</div>
            <div style="font-size:13px;color:#0f172a;font-weight:600;">{_html.escape(summary['priority_action'])}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _severity_for_score(score: int) -> str:
    """Map a 0-100 dimension score to a Severity label. Mirrors the same
    thresholds already used for RAG status (>=80 / 60-79 / <60) — no new
    thresholds are introduced."""
    if score < 60:
        return "HIGH"
    if score < 80:
        return "MEDIUM"
    return "LOW"


def _render_top_summary(model: "ExecutiveDashboard", hs_result: dict) -> None:
    """Top summary strip: Repository Health Score · Overall Status ·
    Migration Coverage · Top Issues · Estimated Effort.

    Built entirely from data already computed elsewhere (get_health_score(),
    ExecutiveDashboard) — no new scoring logic.
    """
    overall_score = hs_result.get("overall_score", hs_result.get("health_score", 0))
    overall_status = hs_result.get("overall_status", hs_result.get("risk_level", "RED"))
    issues = hs_result.get("top_issues", [])

    total_jobs = model.total_jobs or 0
    analyzed_jobs = model.analyzed_jobs or 0
    coverage_pct = int(round((analyzed_jobs / total_jobs) * 100)) if total_jobs else 0

    est_hours = model.estimated_hours or "—"
    est_weeks = model.estimated_weeks if model.estimated_weeks not in (None, "") else "—"

    _status_color = {"GREEN": "#15803d", "AMBER": "#b45309", "RED": "#be123c"}.get(overall_status, "#64748b")
    _status_icon = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}.get(overall_status, "⚪")
    _score_color = "#15803d" if overall_score >= 80 else ("#b45309" if overall_score >= 60 else "#be123c")

    cards = [
        {"label": "Repository Health Score", "value": f"{overall_score}/100", "sub": "Weighted composite score", "color": _score_color},
        {"label": "Overall Status", "value": f"{_status_icon} {overall_status.title() if overall_status else '—'}", "sub": "≥80 Green · 60-79 Amber · <60 Red", "color": _status_color},
        {"label": "Migration Coverage", "value": f"{coverage_pct}%", "sub": f"{analyzed_jobs} of {total_jobs} jobs analyzed", "color": "#0369a1"},
        {"label": "Top Issues", "value": str(len(issues)), "sub": "Lowest-scoring dimensions", "color": "#b45309" if issues else "#15803d"},
        {"label": "Estimated Effort", "value": str(est_hours), "sub": f"{est_weeks} wks" if est_weeks != "—" else "Hours", "color": "#6d28d9"},
    ]

    cols = st.columns(len(cards))
    for col, c in zip(cols, cards):
        with col:
            st.markdown(
                f'<div style="background:#fff;border:1px solid #dbe3ef;border-radius:8px;'
                f'border-top:3px solid {c["color"]};padding:10px 12px 8px;min-height:96px;'
                f'box-shadow:0 1px 2px rgba(15,23,42,.05);">'
                f'<div style="font-size:10px;font-weight:800;color:#64748b;text-transform:uppercase;'
                f'letter-spacing:.05em;margin-bottom:4px;">{_html.escape(c["label"])}</div>'
                f'<div style="font-size:24px;font-weight:900;line-height:1;color:{c["color"]};">{_html.escape(str(c["value"]))}</div>'
                f'<div style="font-size:10px;color:#94a3b8;margin-top:4px;">{_html.escape(c["sub"])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_score_breakdown(hs_result: dict) -> None:
    """Score breakdown: Name · Progress bar · Score · Short description.
    Reuses the existing progress-metric visual language already used
    elsewhere in the app (app.ui.design_system_v2.render_progress_metric)."""
    dims = hs_result.get("metric_scores", hs_result.get("dimensions", []))
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:8px;">Score Breakdown</div>',
        unsafe_allow_html=True,
    )
    if not dims:
        empty_state_card("No score breakdown available", "Run repository analysis to populate this section.")
        return
    for d in dims:
        score = d["score"]
        color = "#15803d" if score >= 80 else "#b45309" if score >= 60 else "#be123c"
        pct = max(2, min(100, score))
        st.markdown(
            f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;'
            f'padding:10px 14px;margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;">'
            f'<span style="font-size:13px;font-weight:700;color:#0f172a;">{_html.escape(d["label"])}</span>'
            f'<span style="font-size:13px;font-weight:800;color:{color};">{score}/100</span>'
            f'</div>'
            f'<div style="background:#e2e8f0;border-radius:999px;height:6px;margin-top:6px;overflow:hidden;">'
            f'<div style="width:{pct}%;height:100%;background:{color};border-radius:999px;"></div>'
            f'</div>'
            f'<div style="font-size:11px;color:#64748b;margin-top:5px;">{_html.escape(d["detail"])}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_top_issues_table(hs_result: dict) -> None:
    """Top Issues: Issue · Severity · Impact · Recommendation.
    Built from the same top_issues list already computed by
    app.analyzers.health_score (no new scoring logic) plus static
    Impact/Recommendation copy from _DIMENSION_GUIDANCE."""
    import pandas as pd

    issues = hs_result.get("top_issues", [])
    dims_by_label = {d["label"]: d for d in hs_result.get("metric_scores", hs_result.get("dimensions", []))}

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
        'letter-spacing:.08em;margin-bottom:8px;">Top Issues</div>',
        unsafe_allow_html=True,
    )

    if not issues:
        empty_state_card("No critical issues found", "All scored dimensions are within healthy range.", "success")
        return

    rows = []
    for issue in issues:
        label = issue.get("dimension", "—")
        score = issue.get("score", 0)
        dim = dims_by_label.get(label, {})
        guidance = _DIMENSION_GUIDANCE.get(dim.get("key", ""), {})
        rows.append({
            "Issue": label,
            "Severity": _severity_for_score(score),
            "Impact": guidance.get("impact", issue.get("detail", "—")),
            "Recommendation": guidance.get("recommendation", "Review this dimension in the settings page."),
        })
    styled_dataframe(pd.DataFrame(rows), "executive_top_issues", use_container_width=True, hide_index=True)


def build_executive_dashboard_model() -> ExecutiveDashboard | None:
    """Build the ExecutiveDashboard model from current session-state
    repository analysis data. Returns None if no analysis has been run yet.
    """
    all_jobs = st.session_state.get("last_analysis_jobs")
    if not all_jobs:
        return None
    return ExecutiveDashboard.from_session_data(
        all_jobs=all_jobs,
        readiness=st.session_state.get("readiness_score", {}),
        effort=st.session_state.get("effort_estimate", {}),
        routines=st.session_state.get("routine_analysis", {}),
        joblets=st.session_state.get("joblet_analysis", {}),
    )


def render_executive_dashboard_page() -> None:
    """Entry point for the Executive Dashboard page route."""
    model = build_executive_dashboard_model()
    if model is None:
        empty_state_card(
            "No repository loaded",
            "Upload your Talend ZIP on the Home page first.",
            "warning",
        )
        return

    # Persist the bound model in session state for downstream consumers
    # (report pack, exports, drilldown tables).
    st.session_state["executive_dashboard_model"] = model
    from app.ui.migration_intelligence_dashboard import build_migration_intelligence
    st.session_state["migration_intelligence"] = build_migration_intelligence(
        st.session_state.get("last_analysis_jobs", []),
        st.session_state.get("readiness_score", {}),
    )

    from app.ui.impact_intelligence_dashboard import build_impact_intelligence
    st.session_state["impact_intelligence"] = build_impact_intelligence(
        st.session_state.get("last_analysis_jobs", []),
        migration_intelligence=st.session_state["migration_intelligence"],
        readiness=st.session_state.get("readiness_score", {}),
    )
    from app.ui.upgrade_advisor_dashboard import build_upgrade_advisor
    from app.ui.migration_runbook_dashboard import build_migration_runbook
    from app.ui.framework_intelligence_dashboard import build_framework_intelligence
    _exec_jobs = st.session_state.get("last_analysis_jobs", [])
    if _exec_jobs:
        st.session_state["upgrade_advisor"] = build_upgrade_advisor(_exec_jobs)
        st.session_state["migration_runbook"] = build_migration_runbook(_exec_jobs, st.session_state.get("upgrade_advisor"))
        st.session_state["framework_intelligence"] = build_framework_intelligence(_exec_jobs)

    from app.ui.architecture_intelligence_dashboard import build_architecture_autofix_intelligence
    st.session_state["architecture_autofix_intelligence"] = build_architecture_autofix_intelligence(
        st.session_state.get("last_analysis_jobs", []),
        readiness=st.session_state.get("readiness_score", {}),
        migration_intelligence=st.session_state.get("migration_intelligence"),
        impact_intelligence=st.session_state.get("impact_intelligence"),
    )
    # ── Repository Health (single source of truth — computed once per session) ──
    _hs_result = {}
    try:
        from app.analyzers.health_score import get_health_score
        _hs_result = get_health_score()
    except Exception:
        pass

    if _hs_result:
        st.markdown(
            '<div style="font-size:14px;font-weight:800;color:#0f172a;margin-bottom:8px;">🏥 Repository Health</div>',
            unsafe_allow_html=True,
        )
        _render_executive_summary_card(model, _hs_result)
        _render_top_summary(model, _hs_result)
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        col_breakdown, col_issues = st.columns([3, 2], gap="medium")
        with col_breakdown:
            _render_score_breakdown(_hs_result)
        with col_issues:
            _render_top_issues_table(_hs_result)

        st.divider()

    from app.ui.dashboard import render_executive_dashboard
    render_executive_dashboard()

    # ── Bottom banner — Overall Status only (single readiness indicator) ──────
    # overall_status is GREEN / AMBER / RED derived from the Repository Health
    # Score only (>=80 / 60-79 / <60); same source used in the top summary above.
    _overall_rag = _hs_result.get("overall_status") or st.session_state.get("readiness_score", {}).get("overall", "RED")
    render_rag_banner(
        _overall_rag,
        title="Overall Status",
        subtitle="Derived from Repository Health Score — ≥80 Green · 60-79 Amber · <60 Red",
    )

