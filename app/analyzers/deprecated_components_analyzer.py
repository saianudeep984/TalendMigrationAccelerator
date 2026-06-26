"""
DeprecatedComponentsAnalyzer

Detects deprecated Talend components across a job repository and produces
a structured remediation report.

A component is considered deprecated if it appears in:
  1. DEPRECATED_COMPONENT_MAP  (primary catalog — has replacement + auto_fix flag)
  2. VERSION_COMPATIBILITY[version]["deprecated_components"]  (version-specific list)

Returns
-------
{
  "summary": {
      "total_deprecated_types": int,
      "total_instances": int,
      "total_jobs_impacted": int,
      "total_effort_hours": int,
      "auto_fixable_count": int,
      "manual_count": int,
      "severity": "HIGH" | "MEDIUM" | "LOW"
  },
  "components": [
      {
          "component": str,
          "replacement": str,
          "auto_fix": bool,
          "risk": str,
          "usage_count": int,
          "job_count": int,
          "jobs_impacted": [str],
          "effort_hours": float,
          "deprecated_since": str | None,
          "migration_action": str
      }, ...                      # sorted by risk desc, usage_count desc
  ],
  "per_job": [
      {
          "job_name": str,
          "deprecated": [
              { "component": str, "count": int, "replacement": str,
                "auto_fix": bool, "risk": str }
          ]
      }, ...
  ],
  "auto_fixable": [ <subset of components where auto_fix=True> ],
  "manual_required": [ <subset of components where auto_fix=False> ],
}
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from app.config.component_rules import DEPRECATED_COMPONENT_MAP
from app.config.version_compatibility import VERSION_COMPATIBILITY


# ---------------------------------------------------------------------------
# Risk ranking
# ---------------------------------------------------------------------------

_RISK_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Effort hours per deprecated instance (by risk level)
_EFFORT_BY_RISK: Dict[str, float] = {
    "HIGH": 6.0,
    "MEDIUM": 3.0,
    "LOW": 1.0,
}

# Version-specific deprecation metadata
# Maps component name -> version it was deprecated in
_DEPRECATED_SINCE: Dict[str, str] = {
    "tMysqlInput":       "Talend 7",
    "tMysqlOutput":      "Talend 7",
    "tMysqlRow":         "Talend 7",
    "tMysqlConnection":  "Talend 7",
    "tMysqlCommit":      "Talend 7",
    "tOracleInput":      "Talend 7",
    "tOracleOutput":     "Talend 7",
    "tOracleRow":        "Talend 7",
    "tOracleConnection": "Talend 7",
    "tOracleCommit":     "Talend 7",
    "tMSSqlInput":       "Talend 7",
    "tMSSqlOutput":      "Talend 7",
    "tMSSqlRow":         "Talend 7",
    "tMSSqlConnection":  "Talend 7",
    "tMSSqlCommit":      "Talend 7",
    "tMSSqlClose":       "Talend 7",
    "tMSSqlRollback":    "Talend 7",
    "tBeanShell":        "Talend 6",
    "tJavaFlex":         "Talend 6",
    "tFileInputExcel":   "Talend 8",
    "tFileArchive":      "Talend 7",
    "tMom":              "Talend 6",
    "tESBConsumer":      "Talend 6",
}


def _migration_action(component: str, rule: Dict[str, Any]) -> str:
    replacement = rule.get("replacement", "")
    auto_fix = rule.get("auto_fix", False)
    risk = rule.get("risk", "MEDIUM")
    if auto_fix and replacement:
        return f"Auto-replace with {replacement}"
    if replacement:
        return f"Manually replace with {replacement}"
    if risk == "HIGH":
        return "Manual remediation required — no direct replacement"
    return "Review and update before migration"


def _build_catalog(source_version: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Build the full deprecated-component catalog, merging
    DEPRECATED_COMPONENT_MAP with version-specific lists.
    """
    catalog: Dict[str, Dict[str, Any]] = {}

    # Primary catalog
    for ct, rule in DEPRECATED_COMPONENT_MAP.items():
        catalog[ct] = {
            "replacement": rule.get("replacement", ""),
            "auto_fix": rule.get("auto_fix", False),
            "risk": rule.get("risk", "MEDIUM"),
            "deprecated_since": _DEPRECATED_SINCE.get(ct),
        }

    # Version-specific additions
    if source_version and source_version in VERSION_COMPATIBILITY:
        for ct in VERSION_COMPATIBILITY[source_version].get("deprecated_components", []):
            if ct not in catalog:
                catalog[ct] = {
                    "replacement": "",
                    "auto_fix": False,
                    "risk": "MEDIUM",
                    "deprecated_since": source_version,
                }

    return catalog


# ---------------------------------------------------------------------------
# DeprecatedComponentsAnalyzer
# ---------------------------------------------------------------------------

class DeprecatedComponentsAnalyzer:
    """
    Detect deprecated Talend components in a job repository.

    Usage
    -----
    analyzer = DeprecatedComponentsAnalyzer()
    report   = analyzer.analyze(all_jobs)

    # With source-version-specific detection:
    report   = analyzer.analyze(all_jobs, source_version="Talend 7")
    """

    def analyze(
        self,
        all_jobs: Sequence[Dict[str, Any]],
        source_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan all_jobs for deprecated components.

        Parameters
        ----------
        all_jobs       : Standard TMA job list (entries with 'job_data' key).
        source_version : Optional Talend version string (e.g. "Talend 7")
                         to include version-specific deprecations.

        Returns
        -------
        Structured report dict (see module docstring).
        """
        catalog = _build_catalog(source_version)

        # component_type -> { count, jobs: set }
        usage: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "jobs": set()}
        )

        per_job: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for job in all_jobs:
            job_data = job.get("job_data", job)
            job_name = job_data.get("job_name", "Unknown")
            components = job_data.get("components", [])

            job_counts: Dict[str, int] = defaultdict(int)
            for comp in components:
                ct = comp.get("component_type", "") if isinstance(comp, dict) else str(comp)
                if ct and ct in catalog:
                    job_counts[ct] += 1

            for ct, count in job_counts.items():
                usage[ct]["count"] += count
                usage[ct]["jobs"].add(job_name)
                rule = catalog[ct]
                per_job[job_name].append({
                    "component": ct,
                    "count": count,
                    "replacement": rule["replacement"],
                    "auto_fix": rule["auto_fix"],
                    "risk": rule["risk"],
                })

        # ── Build components list ────────────────────────────────────────
        components_list: List[Dict[str, Any]] = []
        for ct, data in usage.items():
            rule = catalog[ct]
            risk = rule["risk"]
            effort = data["count"] * _EFFORT_BY_RISK.get(risk, 3.0)
            components_list.append({
                "component": ct,
                "replacement": rule["replacement"],
                "auto_fix": rule["auto_fix"],
                "risk": risk,
                "usage_count": data["count"],
                "job_count": len(data["jobs"]),
                "jobs_impacted": sorted(data["jobs"]),
                "effort_hours": effort,
                "deprecated_since": rule.get("deprecated_since"),
                "migration_action": _migration_action(ct, rule),
            })

        components_list.sort(
            key=lambda r: (-_RISK_RANK.get(r["risk"], 0), -r["usage_count"])
        )

        # ── Summary ──────────────────────────────────────────────────────
        total_instances = sum(r["usage_count"] for r in components_list)
        total_jobs = len({j for r in components_list for j in r["jobs_impacted"]})
        total_effort = sum(r["effort_hours"] for r in components_list)
        auto_fixable = [r for r in components_list if r["auto_fix"]]
        manual_required = [r for r in components_list if not r["auto_fix"]]

        if any(r["risk"] == "HIGH" for r in components_list):
            severity = "HIGH"
        elif any(r["risk"] == "MEDIUM" for r in components_list):
            severity = "MEDIUM"
        elif components_list:
            severity = "LOW"
        else:
            severity = "LOW"

        per_job_list = [
            {"job_name": jn, "deprecated": issues}
            for jn, issues in sorted(per_job.items())
        ]

        return {
            "summary": {
                "total_deprecated_types": len(components_list),
                "total_instances": total_instances,
                "total_jobs_impacted": total_jobs,
                "total_effort_hours": total_effort,
                "auto_fixable_count": len(auto_fixable),
                "manual_count": len(manual_required),
                "severity": severity,
            },
            "components": components_list,
            "per_job": per_job_list,
            "auto_fixable": auto_fixable,
            "manual_required": manual_required,
        }
