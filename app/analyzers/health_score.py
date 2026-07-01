"""
Repository Health Score
=======================
Calculates a 0-100 composite score from existing analysed metrics.
No new parsing — all inputs come from session-state / already-computed data.

Single Scoring Engine
---------------------
ALL callers MUST use ``get_health_score()`` which computes the result once per
Streamlit session and caches it under ``st.session_state["repository_health_score"]``.
Never call ``calculate_health_score()`` directly from UI widgets or reports —
use the session-cached accessor instead so the score is only computed once.

Usage
-----
    from app.analyzers.health_score import get_health_score, render_health_score_widget
    result = get_health_score()          # reads from / populates session_state
    render_health_score_widget(result)

Standard output keys
--------------------
    overall_score   : int            # 0-100  (alias for health_score)
    overall_status  : str            # "GREEN" / "AMBER" / "RED"  (>=80 / 60-79 / <60)
    metric_scores   : list[dict]     # per-dimension breakdown (alias for dimensions)
    top_issues      : list[dict]     # top-5 lowest-scoring dimensions
    health_score    : int            # kept for backward-compat (== overall_score)
    risk_level      : str            # kept for backward-compat (== overall_status, GREEN/AMBER/RED)
    dimensions      : list[dict]     # kept for backward-compat (== metric_scores)
"""

from __future__ import annotations

from typing import Any

# Session-state key under which the single shared result is stored.
_SESSION_KEY = "repository_health_score"

# ── Default weights (sum to 1.0) ─────────────────────────────────────────────
# Keep in a single dict so callers / settings UI can override them.
DEFAULT_WEIGHTS: dict[str, float] = {
    "migration_readiness": 0.25,
    "complexity":          0.15,
    "sql_risk":            0.15,
    "java_risk":           0.15,
    "documentation":       0.10,
    "deprecated":          0.10,
    "error_count":         0.10,
}


# ── Per-dimension score extractors ────────────────────────────────────────────

def _score_migration_readiness(all_jobs: list, readiness_score: dict) -> tuple[int, str]:
    """0-100 from RepositoryScoring migration_readiness_score."""
    try:
        from app.analyzers.readiness_scorer import RepositoryScoring
        scoring = RepositoryScoring().score(all_jobs)
        s = int(scoring.get("migration_readiness_score", 50))
        return s, f"Migration readiness score: {s}/100"
    except Exception:
        # Fallback: map RAG overall to rough score
        rag = readiness_score.get("overall", "AMBER")
        s = {"GREEN": 85, "AMBER": 55, "RED": 20}.get(rag, 50)
        return s, f"RAG overall: {rag}"


def _score_complexity(all_jobs: list) -> tuple[int, str]:
    """0-100 (higher = lower complexity = better health)."""
    try:
        from app.analyzers.readiness_scorer import RepositoryScoring
        scoring = RepositoryScoring().score(all_jobs)
        raw = int(scoring.get("repository_complexity_score", 50))
        # Invert: low complexity → high score
        s = max(0, 100 - raw)
        return s, f"Complexity score: {raw}/100 (inverted → {s})"
    except Exception:
        total = max(1, len(all_jobs))
        avg = sum(
            j.get("complexity", {}).get("score", 50) for j in all_jobs
        ) / total
        s = max(0, 100 - int(avg))
        return s, f"Avg job complexity: {avg:.0f}"


def _score_sql_risk(all_jobs: list) -> tuple[int, str]:
    """0-100 (higher = lower SQL risk = better health)."""
    try:
        from app.parser.source_target_extractor import extract_sql_operations
        total_sql = sum(
            len(extract_sql_operations(j.get("job_data", {}).get("components", [])))
            for j in all_jobs
        )
        total_jobs = max(1, len(all_jobs))
        # Scale: ≥2 SQL ops per job on average = 0, 0 = 100
        avg = total_sql / total_jobs
        s = max(0, int(100 - min(100, avg * 25)))
        return s, f"{total_sql} SQL operations across {total_jobs} jobs"
    except Exception:
        return 70, "SQL operations unavailable"


def _score_java_risk(all_jobs: list) -> tuple[int, str]:
    """0-100 (higher = lower Java risk = better health)."""
    try:
        from app.analyzers.java_risk_analyzer import analyze_java_risks
        result = analyze_java_risks(tuple(id(j) for j in all_jobs)  # bypass cache key
                                    if False else all_jobs)
        repo_risk = result.get("risk_score", 0)  # 0–100: higher = more risk
        s = max(0, 100 - repo_risk)
        summary = result.get("summary", {})
        detail = (
            f"{summary.get('total_java_jobs', 0)} Java jobs; "
            f"{summary.get('critical', 0)} critical, {summary.get('high', 0)} high"
        )
        return s, detail
    except Exception:
        return 80, "Java risk data unavailable"


def _score_documentation(all_jobs: list) -> tuple[int, str]:
    """0-100 from documentation_readiness_score."""
    try:
        from app.analyzers.readiness_scorer import RepositoryScoring
        scoring = RepositoryScoring().score(all_jobs)
        s = int(scoring.get("documentation_readiness_score", 50))
        return s, f"Documentation score: {s}/100"
    except Exception:
        return 50, "Documentation data unavailable"


def _score_deprecated(deprecated_rows: list) -> tuple[int, str]:
    """0-100 (higher = fewer deprecated usages = better health)."""
    total = sum(r.get("count", 0) for r in (deprecated_rows or []))
    s = max(0, int(100 - min(100, total * 3)))
    return s, f"{total} deprecated component usage(s)"


def _score_error_count(all_jobs: list, readiness_score: dict) -> tuple[int, str]:
    """0-100 based on HIGH/CRITICAL risk findings count."""
    try:
        errors = sum(
            1
            for j in all_jobs
            for r in j.get("enterprise_risk_report", [])
            if r.get("risk") in ("HIGH", "CRITICAL")
        )
        s = max(0, int(100 - min(100, errors * 4)))
        return s, f"{errors} HIGH/CRITICAL risk finding(s)"
    except Exception:
        return 70, "Error data unavailable"


# ── Top-issues extractor ───────────────────────────────────────────────────────

def _top_issues(dimension_scores: list[dict]) -> list[dict]:
    """Return top 5 lowest-scoring dimensions as actionable issues."""
    sorted_dims = sorted(dimension_scores, key=lambda d: d["score"])
    issues = []
    for d in sorted_dims[:5]:
        score = d["score"]
        level = "RED" if score < 60 else "AMBER" if score < 80 else "GREEN"
        issues.append({
            "dimension": d["label"],
            "score": score,
            "detail": d["detail"],
            "level": level,
            "icon": {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}[level],
        })
    return issues


# ── Canonical helpers (single source of truth for ALL callers) ────────────────

def rag_from_score(score: int, *, low: int = 60, high: int = 80) -> str:
    """Convert a 0-100 numeric score to RED / AMBER / GREEN.

    Canonical thresholds (configurable, default canonical):
        score >= 80  → GREEN
        score >= 60  → AMBER
        score <  60  → RED

    All UI pages, reports, and export writers MUST call this function
    instead of defining their own inline rag/threshold logic.
    """
    try:
        s = int(score)
    except (TypeError, ValueError):
        return "AMBER"
    if s >= high:
        return "GREEN"
    if s >= low:
        return "AMBER"
    return "RED"


def effort_from_complexity_distribution(
    complexity_high: int = 0,
    complexity_critical: int = 0,
    complexity_low: int = 0,
    complexity_medium: int = 0,
    *,
    manual_hours_per_job: int = 8,
    auto_hours_per_job: int = 2,
) -> dict:
    """Derive effort estimate from complexity distribution counts.

    Returns:
        { "total_hours": int, "total_weeks": float }

    All callers that need effort-from-complexity MUST use this function
    rather than computing hours/weeks inline.
    """
    manual_jobs = complexity_high + complexity_critical
    auto_jobs = complexity_low + complexity_medium
    hours = manual_jobs * manual_hours_per_job + auto_jobs * auto_hours_per_job
    weeks = round(hours / 40, 1)
    return {"total_hours": hours, "total_weeks": weeks}


# ── Public API ─────────────────────────────────────────────────────────────────

def calculate_health_score(
    all_jobs: list,
    readiness_score: dict | None = None,
    deprecated_rows: list | None = None,
    weights: dict[str, float] | None = None,
) -> dict:
    """
    Calculate composite Repository Health Score.

    Do NOT call this directly from UI widgets or reports.
    Use ``get_health_score()`` instead so the score is computed only once
    per session and all callers share the identical result.

    Returns
    -------
    {
      # ── Canonical keys (preferred) ──────────────────────────────────────
      "overall_score":  int,         # 0-100 weighted composite
      "overall_status": str,         # "GREEN" / "AMBER" / "RED" derived from overall_score only
      "metric_scores":  list[dict],  # per-dimension breakdown
      "top_issues":     list[dict],  # top-5 lowest-scoring dimensions

      # ── Backward-compat aliases (equal to canonical keys above) ─────────
      "health_score":   int,         # == overall_score
      "risk_level":     str,         # == overall_status
      "dimensions":     list[dict],  # == metric_scores

      "weights_used":        dict,
    }
    """
    readiness_score = readiness_score or {}
    deprecated_rows = deprecated_rows or []
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    # Normalise weights in case caller supplied partial overrides
    total_w = sum(w.values()) or 1.0
    w = {k: v / total_w for k, v in w.items()}

    mr_score,   mr_detail   = _score_migration_readiness(all_jobs, readiness_score)
    cx_score,   cx_detail   = _score_complexity(all_jobs)
    sql_score,  sql_detail  = _score_sql_risk(all_jobs)
    java_score, java_detail = _score_java_risk(all_jobs)
    doc_score,  doc_detail  = _score_documentation(all_jobs)
    dep_score,  dep_detail  = _score_deprecated(deprecated_rows)
    err_score,  err_detail  = _score_error_count(all_jobs, readiness_score)

    dimensions = [
        {"key": "migration_readiness", "label": "Migration Readiness", "score": mr_score,   "weight": w["migration_readiness"], "detail": mr_detail},
        {"key": "complexity",          "label": "Complexity",          "score": cx_score,   "weight": w["complexity"],          "detail": cx_detail},
        {"key": "sql_risk",            "label": "SQL Risk",            "score": sql_score,  "weight": w["sql_risk"],            "detail": sql_detail},
        {"key": "java_risk",           "label": "Java Risk",           "score": java_score, "weight": w["java_risk"],           "detail": java_detail},
        {"key": "documentation",       "label": "Documentation",       "score": doc_score,  "weight": w["documentation"],       "detail": doc_detail},
        {"key": "deprecated",          "label": "Deprecated Components","score": dep_score, "weight": w["deprecated"],          "detail": dep_detail},
        {"key": "error_count",         "label": "Error Count",         "score": err_score,  "weight": w["error_count"],         "detail": err_detail},
    ]

    health_score = int(sum(d["score"] * d["weight"] for d in dimensions))
    health_score = max(0, min(100, health_score))

    # Overall Status — derived from Overall Health Score only.
    # Thresholds: >=80 GREEN, 60-79 AMBER, <60 RED.
    # This is the single authoritative status for Repository Health.
    if health_score >= 80:
        overall_status = "GREEN"
    elif health_score >= 60:
        overall_status = "AMBER"
    else:
        overall_status = "RED"

    # Migration Readiness has its own independent score and status.
    # mr_score is one dimension of the composite; it gets its own RAG here.
    if mr_score >= 80:
        mr_status = "GREEN"
    elif mr_score >= 60:
        mr_status = "AMBER"
    else:
        mr_status = "RED"

    computed_top_issues = _top_issues(dimensions)

    return {
        # ── Canonical keys ────────────────────────────────────────────────
        "overall_score":             health_score,    # 0-100 composite
        "overall_status":            overall_status,  # GREEN / AMBER / RED from overall_score only
        "metric_scores":             dimensions,      # per-dimension breakdown
        "top_issues":               computed_top_issues,
        # ── Migration Readiness — independent score & status ──────────────
        "migration_readiness_score": mr_score,        # 0-100, one input dimension
        "migration_readiness_status": mr_status,      # GREEN / AMBER / RED independent of overall
        # ── Backward-compat aliases ───────────────────────────────────────
        "health_score":              health_score,    # == overall_score
        "risk_level":                overall_status,  # == overall_status (GREEN/AMBER/RED)
        "dimensions":                dimensions,      # == metric_scores
        "weights_used":              w,
    }


# ── Streamlit widget ───────────────────────────────────────────────────────────

def render_health_score_widget(result: dict, compact: bool = False) -> None:
    """Render the health score as a Streamlit component. Import-guarded."""
    import streamlit as st

    score   = result.get("overall_score", result.get("health_score", 0))
    status  = result.get("overall_status", result.get("risk_level", "RED"))
    mr_score  = result.get("migration_readiness_score", 0)
    mr_status = result.get("migration_readiness_status", "RED")
    issues  = result.get("top_issues", [])
    dims    = result.get("metric_scores", result.get("dimensions", []))

    # ── Colour palette — keyed by GREEN / AMBER / RED ─────────────────────
    _SCORE_COLOR = (
        "#15803d" if score >= 80 else
        "#b45309" if score >= 60 else
        "#be123c"
    )
    _STATUS_BG = {
        "GREEN": ("#f0fdf4", "#86efac", "#15803d"),
        "AMBER": ("#fffbeb", "#fcd34d", "#b45309"),
        "RED":   ("#fff1f2", "#fda4af", "#be123c"),
    }
    _STATUS_ICON  = {"GREEN": "🟢", "AMBER": "🟡", "RED": "🔴"}
    _STATUS_LABEL = {"GREEN": "Green", "AMBER": "Amber", "RED": "Red"}
    bg, bd, fg = _STATUS_BG.get(status, ("#f8fafc", "#cbd5e1", "#64748b"))
    icon        = _STATUS_ICON.get(status, "⚪")
    status_lbl  = _STATUS_LABEL.get(status, status)
    mr_icon     = _STATUS_ICON.get(mr_status, "⚪")
    mr_lbl      = _STATUS_LABEL.get(mr_status, mr_status)

    # ── Hero score card ──────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:linear-gradient(118deg,#0f172a 0%,#1e3a5f 60%,#1d4ed8 100%);
        border-radius:16px;padding:24px 28px;color:#fff;margin-bottom:16px;">
          <div style="font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
          color:rgba(255,255,255,.6);margin-bottom:6px;">Repository Health</div>
          <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap;">
            <div style="text-align:center;">
              <div style="font-size:56px;font-weight:900;line-height:1;color:{_SCORE_COLOR};">{score}</div>
              <div style="font-size:11px;color:rgba(255,255,255,.6);margin-top:2px;">/ 100</div>
            </div>
            <div style="flex:1;min-width:180px;">
              <div style="display:inline-flex;align-items:center;gap:6px;
              background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);
              border-radius:999px;padding:5px 14px;margin-bottom:10px;">
                <span style="font-size:14px;">{icon}</span>
                <span style="font-size:13px;font-weight:700;">Overall Status — {status_lbl}</span>
              </div>
              <div style="display:flex;gap:16px;flex-wrap:wrap;">
                <div>
                  <div style="font-size:18px;font-weight:800;">{mr_icon} {mr_score}</div>
                  <div style="font-size:11px;color:rgba(255,255,255,.6);">Migration Readiness ({mr_lbl})</div>
                </div>
                <div>
                  <div style="font-size:18px;font-weight:800;">{len(issues)}</div>
                  <div style="font-size:11px;color:rgba(255,255,255,.6);">Top Issues</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Dimension bars + Top Issues side by side ─────────────────────────────
    col_dims, col_issues = st.columns([3, 2], gap="medium")

    with col_dims:
        st.markdown(
            '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
            'letter-spacing:.08em;margin-bottom:8px;">Score Breakdown</div>',
            unsafe_allow_html=True,
        )
        for d in dims:
            ds = d["score"]
            bar_color = "#15803d" if ds >= 80 else "#b45309" if ds >= 60 else "#be123c"
            pct = max(2, ds)
            st.markdown(
                f"""
                <div style="margin-bottom:8px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-bottom:3px;">
                    <span style="font-size:12px;font-weight:600;color:#334155;">{d['label']}</span>
                    <span style="font-size:12px;font-weight:800;color:{bar_color};">{ds}</span>
                  </div>
                  <div style="background:#e2e8f0;border-radius:999px;height:6px;overflow:hidden;">
                    <div style="width:{pct}%;height:100%;background:{bar_color};
                    border-radius:999px;transition:width .3s;"></div>
                  </div>
                  <div style="font-size:10px;color:#94a3b8;margin-top:2px;">{d['detail']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with col_issues:
        st.markdown(
            '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
            'letter-spacing:.08em;margin-bottom:8px;">Top 5 Issues</div>',
            unsafe_allow_html=True,
        )
        if not issues:
            st.markdown(
                '<div style="font-size:12px;color:#64748b;padding:12px;'
                'background:#f8fafc;border-radius:10px;">✅ No critical issues found</div>',
                unsafe_allow_html=True,
            )
        else:
            for i, issue in enumerate(issues, 1):
                lvl_bg = {
                    "RED": "#fff1f2", "AMBER": "#fffbeb", "GREEN": "#f0fdf4"
                }.get(issue["level"], "#f8fafc")
                lvl_bd = {
                    "RED": "#fda4af", "AMBER": "#fcd34d", "GREEN": "#86efac"
                }.get(issue["level"], "#e2e8f0")
                lvl_fg = {
                    "RED": "#be123c", "AMBER": "#b45309", "GREEN": "#15803d"
                }.get(issue["level"], "#475569")
                st.markdown(
                    f"""
                    <div style="background:{lvl_bg};border:1px solid {lvl_bd};border-left:3px solid {lvl_fg};
                    border-radius:8px;padding:8px 12px;margin-bottom:6px;">
                      <div style="font-size:12px;font-weight:700;color:{lvl_fg};">
                        {issue['icon']} #{i} {issue['dimension']}
                        <span style="font-weight:800;float:right;">{issue['score']}/100</span>
                      </div>
                      <div style="font-size:10px;color:#64748b;margin-top:2px;">{issue['detail']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ── Session-cached singleton accessor ─────────────────────────────────────────

def get_health_score(
    weights: dict[str, float] | None = None,
    *,
    force_refresh: bool = False,
) -> dict:
    """
    Return the canonical Repository Health Score, computing it at most once
    per Streamlit session.

    All UI widgets and reports MUST call this function instead of calling
    ``calculate_health_score()`` directly.  The result is stored under
    ``st.session_state["repository_health_score"]`` so every consumer—
    Executive Dashboard, Home page, and exported reports—shares the identical
    object without re-running the scoring logic.

    Parameters
    ----------
    weights       : Optional weight overrides (forwarded to calculate_health_score).
    force_refresh : When True the cached result is discarded and recomputed.

    Returns
    -------
    Same dict as ``calculate_health_score()`` (see its docstring for keys).
    Returns an empty dict ``{}`` when no repository has been loaded yet.
    """
    import streamlit as st

    all_jobs = st.session_state.get("last_analysis_jobs")
    if not all_jobs:
        return {}

    cached = st.session_state.get(_SESSION_KEY)
    if cached is not None and not force_refresh:
        return cached

    result = calculate_health_score(
        all_jobs=all_jobs,
        readiness_score=st.session_state.get("readiness_score", {}),
        deprecated_rows=st.session_state.get("deprecated_rows", []),
        weights=weights,
    )
    st.session_state[_SESSION_KEY] = result
    return result
