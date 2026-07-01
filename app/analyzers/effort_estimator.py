"""
Repository-wide Migration Effort Estimator
"""


def _job_unit_counts(job):
    """Components / SQL ops / dependencies / custom-code units for one job.
    Mirrors the per-job counters used by the Effort Estimation settings
    preview (app/ui/streamlit_app.py) so the repository-wide total and the
    settings live-preview always agree."""
    from app.parser.source_target_extractor import extract_sql_operations

    job_data = job.get("job_data", {})
    components = job_data.get("components", [])
    n_components = len(components)
    n_sql = len(extract_sql_operations(components))
    n_deps = len(job.get("dependencies", {}).get("child_jobs", []))
    n_custom = sum(1 for c in components if "java" in str(c.get("component_type", "")).lower())
    return n_components, n_sql, n_deps, n_custom


def _rate_driven_hours(all_jobs, rates) -> float:
    """Sum (components × h/comp) + (sql × h/sql) + (deps × h/dep) +
    (custom × h/custom) across every job, using the configured rates —
    same formula as the Effort Estimation settings page."""
    h_comp = rates.get("hours_per_component", 0.5)
    h_sql = rates.get("hours_per_sql_query", 1.0)
    h_dep = rates.get("hours_per_dependency", 0.5)
    h_custom = rates.get("hours_per_custom_code", 2.0)

    total_hours = 0.0
    for job in all_jobs:
        n_components, n_sql, n_deps, n_custom = _job_unit_counts(job)
        total_hours += (
            n_components * h_comp + n_sql * h_sql + n_deps * h_dep + n_custom * h_custom
        )
    return total_hours


def estimate_repository_effort(all_jobs, custom_analysis, deprecated_rows, rates=None):
    """
    Produce repository-level effort estimate.

    Args:
        rates: optional dict with hours_per_component, hours_per_sql_query,
            hours_per_dependency, hours_per_custom_code — the same keys used
            by the "Effort Estimation" settings page. When provided, hours
            are computed bottom-up from each job's actual component/SQL/
            dependency/custom-code counts (live, configurable). When omitted,
            falls back to the legacy flat auto=2h / manual=8h heuristic for
            backward compatibility.

    Returns:
        {
          total_jobs, auto_migratable, manual_required,
          auto_pct, manual_pct,
          estimated_days, estimated_weeks,
          high_risk_jobs, by_complexity
        }
    """

    total = len(all_jobs)
    if total == 0:
        return {}

    manual_jobs = set()
    auto_jobs = set()

    # Jobs with custom components → manual
    for comp_data in custom_analysis.get("custom_components", []):
        for j in comp_data["jobs_impacted"]:
            manual_jobs.add(j)

    # Jobs with non-auto-fixable deprecated → manual
    for row in deprecated_rows:
        if not row["auto_fix"]:
            for j in row["impacted_jobs"]:
                manual_jobs.add(j)

    # Remaining → auto-migratable
    all_names = {j["job_data"]["job_name"] for j in all_jobs}
    auto_jobs = all_names - manual_jobs

    auto_pct = round(len(auto_jobs) / total * 100, 1)
    manual_pct = round(len(manual_jobs) / total * 100, 1)

    if rates:
        total_hours = round(_rate_driven_hours(all_jobs, rates), 1)
    else:
        # Legacy flat heuristic: auto=2h, manual=8h average per job
        total_hours = len(auto_jobs) * 2 + len(manual_jobs) * 8

    total_days = round(total_hours / 8, 1)
    total_weeks = round(total_days / 5, 1)

    # Complexity breakdown
    by_complexity = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    high_risk_jobs = []

    for job in all_jobs:
        c = job.get("estimation", {}).get("complexity", "LOW")
        by_complexity[c] = by_complexity.get(c, 0) + 1
        if c in ("HIGH", "CRITICAL"):
            high_risk_jobs.append(job["job_data"]["job_name"])

    return {
        "total_jobs": total,
        "auto_migratable": len(auto_jobs),
        "manual_required": len(manual_jobs),
        "auto_pct": auto_pct,
        "manual_pct": manual_pct,
        "estimated_hours": total_hours,
        "estimated_days": total_days,
        "estimated_weeks": total_weeks,
        "high_risk_jobs": high_risk_jobs,
        "by_complexity": by_complexity
    }


def live_repository_effort_estimate():
    """Recompute the repository-wide effort estimate from whatever is
    currently in session state — analyzed jobs AND the live Effort
    Estimation rates. Call this anywhere the Estimated Effort / Estimated
    Savings KPIs are displayed so they always reflect the latest saved (or
    unsaved-but-edited) settings instead of a stale value cached from the
    last full analysis run. Returns {} if no repository has been analyzed.
    """
    import streamlit as st
    from app.config.assessment_config_store import DEFAULT_CONFIG as _ASSESSMENT_DEFAULT_CONFIG

    all_jobs = st.session_state.get("last_analysis_jobs")
    if not all_jobs:
        return {}

    custom_analysis = st.session_state.get("custom_analysis", {})
    deprecated_rows = st.session_state.get("deprecated_rows", [])
    cfg = st.session_state.get("assessment_config", _ASSESSMENT_DEFAULT_CONFIG)
    rates = cfg.get("effort", _ASSESSMENT_DEFAULT_CONFIG["effort"])

    return estimate_repository_effort(all_jobs, custom_analysis, deprecated_rows, rates=rates)
