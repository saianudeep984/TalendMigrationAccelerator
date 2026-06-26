"""
Repository-wide Migration Effort Estimator
"""


def estimate_repository_effort(all_jobs, custom_analysis, deprecated_rows):
    """
    Produce repository-level effort estimate.

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

    # Hours: auto=2h, manual=8h average
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
