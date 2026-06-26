"""
Deprecated Component Dashboard Data Builder
"""

from collections import defaultdict
from app.config.component_rules import DEPRECATED_COMPONENT_MAP


def build_deprecated_dashboard(all_jobs):
    """
    Scan all jobs for deprecated components.

    Returns list of rows:
        { component, count, impacted_jobs, replacement, auto_fix, risk }
    """

    comp_usage = defaultdict(lambda: {"count": 0, "jobs": set()})

    for job in all_jobs:
        job_name = job["job_data"]["job_name"]
        for comp in job["job_data"]["components"]:
            ctype = comp["component_type"]
            if ctype in DEPRECATED_COMPONENT_MAP:
                comp_usage[ctype]["count"] += 1
                comp_usage[ctype]["jobs"].add(job_name)

    rows = []
    for ctype, data in sorted(comp_usage.items(),
                               key=lambda x: -x[1]["count"]):
        rule = DEPRECATED_COMPONENT_MAP[ctype]
        rows.append({
            "component": ctype,
            "count": data["count"],
            "impacted_jobs": sorted(data["jobs"]),
            "replacement": rule["replacement"],
            "auto_fix": rule["auto_fix"],
            "risk": rule["risk"]
        })

    return rows
