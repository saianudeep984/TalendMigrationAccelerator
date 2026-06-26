"""
Unsupported Component Analyzer
Detects components that require manual remediation for Talend Cloud migration:
  - tJava* (tJava, tJavaRow, tJavaFlex)
  - tSystem
  - Custom Routines
  - Custom JDBC drivers
"""

from collections import defaultdict
from typing import Any, Dict, Sequence

# ── Detection sets ──────────────────────────────────────────────────────────

_JAVA_COMPONENTS = {"tJava", "tJavaRow", "tJavaFlex"}

_SYSTEM_COMPONENTS = {"tSystem", "tLibraryLoad", "tBeanShell", "tGroovy",
                      "tPythonRow", "tRubyRow"}

# JDBC components that imply a custom driver (not a named DB connector)
_CUSTOM_JDBC_COMPONENTS = {
    "tJDBCInput", "tJDBCOutput", "tJDBCRow",
    "tJDBCConnection", "tJDBCCommit", "tJDBCClose", "tJDBCRollback",
}

# ── Impact scoring ──────────────────────────────────────────────────────────

_CATEGORY_META = {
    "tJava*": {
        "icon": "☕",
        "severity": "HIGH",
        "effort_hours_per_instance": 8,
        "description": "Inline Java code blocks require rewrite or extraction to custom routines.",
        "recommendation": "Extract to a shared Custom Routine or replace with tMap expression logic.",
        "color": "#b45309",
    },
    "tSystem": {
        "icon": "💻",
        "severity": "CRITICAL",
        "effort_hours_per_instance": 12,
        "description": "OS command execution is unsupported in Talend Cloud serverless runtime.",
        "recommendation": "Replace with a REST API call, cloud function, or managed service trigger.",
        "color": "#be123c",
    },
    "Custom Routines": {
        "icon": "📋",
        "severity": "MEDIUM",
        "effort_hours_per_instance": 4,
        "description": "Custom Java routines may reference file system, runtime, or unsupported APIs.",
        "recommendation": "Audit each routine for cloud-unsafe patterns and refactor or remove.",
        "color": "#6d28d9",
    },
    "Custom JDBC": {
        "icon": "🔌",
        "severity": "HIGH",
        "effort_hours_per_instance": 6,
        "description": "Generic JDBC connectors require custom driver JARs not available in cloud runtime.",
        "recommendation": "Replace with a named cloud-native connector (tSnowflakeInput, tBigQueryInput, etc.).",
        "color": "#0369a1",
    },
}


# ── Core analysis ────────────────────────────────────────────────────────────

def analyze_unsupported_components(
    all_jobs: Sequence[Dict[str, Any]],
    routine_analysis: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Scan all_jobs for unsupported components and return a structured report.

    Parameters
    ----------
    all_jobs         : TMA standard job list from session state
    routine_analysis : result of analyze_routines() (optional, enriches routines section)

    Returns
    -------
    {
      "summary": {total_instances, total_jobs_impacted, total_effort_hours, severity},
      "categories": {
          "tJava*":          {"count", "jobs", "instances", "effort_hours"},
          "tSystem":         {...},
          "Custom Routines": {...},
          "Custom JDBC":     {...},
      },
      "per_job": [ {job_name, issues: [{category, component_type, count}]} ],
    }
    """

    # Track per category: count of instances, set of impacted jobs, per-job detail
    cats: dict[str, dict] = {
        key: {"count": 0, "jobs": set(), "instances": []}
        for key in _CATEGORY_META
    }

    per_job: dict[str, list] = defaultdict(list)

    for job in all_jobs:
        job_name   = job["job_data"]["job_name"]
        components = job["job_data"].get("components", [])

        # Count per component_type within this job
        type_counts: dict[str, int] = defaultdict(int)
        for comp in components:
            ct = comp.get("component_type", "")
            type_counts[ct] += 1

        # ── tJava* ──────────────────────────────────────────────────────
        java_total = sum(type_counts[ct] for ct in _JAVA_COMPONENTS if ct in type_counts)
        if java_total:
            cats["tJava*"]["count"] += java_total
            cats["tJava*"]["jobs"].add(job_name)
            cats["tJava*"]["instances"].append({
                "job": job_name,
                "count": java_total,
                "breakdown": {ct: type_counts[ct] for ct in _JAVA_COMPONENTS if ct in type_counts},
            })
            per_job[job_name].append({"category": "tJava*", "count": java_total})

        # ── tSystem ─────────────────────────────────────────────────────
        sys_total = sum(type_counts[ct] for ct in _SYSTEM_COMPONENTS if ct in type_counts)
        if sys_total:
            cats["tSystem"]["count"] += sys_total
            cats["tSystem"]["jobs"].add(job_name)
            cats["tSystem"]["instances"].append({
                "job": job_name,
                "count": sys_total,
                "breakdown": {ct: type_counts[ct] for ct in _SYSTEM_COMPONENTS if ct in type_counts},
            })
            per_job[job_name].append({"category": "tSystem", "count": sys_total})

        # ── Custom JDBC ─────────────────────────────────────────────────
        jdbc_total = sum(type_counts[ct] for ct in _CUSTOM_JDBC_COMPONENTS if ct in type_counts)
        if jdbc_total:
            cats["Custom JDBC"]["count"] += jdbc_total
            cats["Custom JDBC"]["jobs"].add(job_name)
            cats["Custom JDBC"]["instances"].append({
                "job": job_name,
                "count": jdbc_total,
                "breakdown": {ct: type_counts[ct] for ct in _CUSTOM_JDBC_COMPONENTS if ct in type_counts},
            })
            per_job[job_name].append({"category": "Custom JDBC", "count": jdbc_total})

    # ── Custom Routines (from routine_analysis if available) ─────────────
    if routine_analysis:
        routines = routine_analysis.get("routines", [])
        for r in routines:
            risk  = r.get("risk_level", "LOW")
            jobs  = r.get("jobs_using", [])
            count = max(1, r.get("job_count", len(jobs)))
            cats["Custom Routines"]["count"] += count
            cats["Custom Routines"]["jobs"].update(jobs)
            cats["Custom Routines"]["instances"].append({
                "routine": r.get("name", "—"),
                "risk": risk,
                "jobs": jobs,
                "count": count,
                "risks": r.get("risks", []),
            })
            for jn in jobs:
                per_job[jn].append({"category": "Custom Routines", "count": 1})

    # ── Totals ───────────────────────────────────────────────────────────
    total_instances    = sum(v["count"] for v in cats.values())
    total_jobs_impacted = len({j for v in cats.values() for j in v["jobs"]})
    total_effort       = sum(
        cats[k]["count"] * _CATEGORY_META[k]["effort_hours_per_instance"]
        for k in cats
    )

    # Overall severity
    if cats["tSystem"]["count"] > 0:
        severity = "CRITICAL"
    elif cats["tJava*"]["count"] > 0 or cats["Custom JDBC"]["count"] > 0:
        severity = "HIGH"
    elif cats["Custom Routines"]["count"] > 0:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    # Serialise job sets to sorted lists
    for v in cats.values():
        v["jobs"] = sorted(v["jobs"])
        v["job_count"] = len(v["jobs"])
        v["effort_hours"] = v["count"] * _CATEGORY_META[
            next(k for k, cv in cats.items() if cv is v)
        ]["effort_hours_per_instance"] if False else 0  # placeholder, fixed below

    for key in cats:
        cats[key]["effort_hours"] = (
            cats[key]["count"] * _CATEGORY_META[key]["effort_hours_per_instance"]
        )

    per_job_list = [
        {"job_name": jn, "issues": issues}
        for jn, issues in sorted(per_job.items())
    ]

    return {
        "summary": {
            "total_instances":     total_instances,
            "total_jobs_impacted": total_jobs_impacted,
            "total_effort_hours":  total_effort,
            "severity":            severity,
        },
        "categories": cats,
        "meta": _CATEGORY_META,
        "per_job": per_job_list,
    }
