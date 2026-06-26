"""
UnsupportedMigrationComponentsAnalyzer

Detects Talend components that cannot be migrated as-is to Talend 8 or
Talend Cloud.  Consolidates four sources:

  1. HARD_BLOCKERS   — removed in Talend 8; migration is blocked
  2. CLOUD_BLOCKERS  — unsupported in Talend Cloud serverless runtime
  3. VERSION_UNSUPPORTED — version_matrix removed_components + version_compatibility
  4. SOFT_BLOCKERS   — present but may need manual adjustment

Returns
-------
{
  "summary": {
      "total_unsupported_types": int,
      "total_instances": int,
      "total_jobs_impacted": int,
      "hard_blocker_count": int,
      "cloud_blocker_count": int,
      "soft_blocker_count": int,
      "migration_blocked": bool,
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
  },
  "hard_blockers": [ {component, usage_count, jobs_impacted, reason,
                       replacement, effort_hours} ],
  "cloud_blockers": [ {component, usage_count, jobs_impacted, reason,
                        replacement, effort_hours} ],
  "soft_blockers":  [ {component, usage_count, jobs_impacted, reason,
                        replacement, effort_hours} ],
  "per_job": [
      { "job_name": str,
        "hard_blockers": [...], "cloud_blockers": [...], "soft_blockers": [...] }
  ],
  "all_unsupported": [   # merged, sorted by severity desc then usage desc
      { component, category, severity, usage_count, jobs_impacted,
        reason, replacement, effort_hours }
  ]
}
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from app.config.version_compatibility import VERSION_COMPATIBILITY
from app.config.version_matrix import VERSION_UPGRADE_MATRIX

# ---------------------------------------------------------------------------
# Master unsupported-component catalog
# ---------------------------------------------------------------------------

# Components completely removed in Talend 8 — hard migration blockers
_HARD_BLOCKERS: Dict[str, Dict[str, Any]] = {
    "tJavaFlex":        {"reason": "Removed in Talend 8",          "replacement": "tJavaRow",   "effort": 8},
    "tPigLoad":         {"reason": "Pig engine removed",           "replacement": "",           "effort": 16},
    "tPigStore":        {"reason": "Pig engine removed",           "replacement": "",           "effort": 16},
    "tPigStoreResult":  {"reason": "Pig engine removed",           "replacement": "",           "effort": 16},
    "tHiveLoad":        {"reason": "Hive batch mode removed",      "replacement": "tHiveInput", "effort": 12},
    "tELTMap":          {"reason": "ELT components removed in T8", "replacement": "tMap",       "effort": 10},
    "tELTInput":        {"reason": "ELT components removed in T8", "replacement": "tDBInput",   "effort": 10},
    "tELTOutput":       {"reason": "ELT components removed in T8", "replacement": "tDBOutput",  "effort": 10},
    "tMom":             {"reason": "MOM connector removed",        "replacement": "tActiveMQInput / tKafkaInput", "effort": 8},
    "tSparkLoad":       {"reason": "Direct Spark load removed",    "replacement": "tSparkConfiguration", "effort": 12},
}

# Components that work in Talend 8 Studio but are blocked in Talend Cloud
_CLOUD_BLOCKERS: Dict[str, Dict[str, Any]] = {
    "tSystem":       {"reason": "OS execution unsupported in Cloud runtime",  "replacement": "Cloud function / REST API", "effort": 12},
    "tLibraryLoad":  {"reason": "JAR loading unsupported in Cloud runtime",   "replacement": "Bundle JAR in project",    "effort": 6},
    "tJava":         {"reason": "Inline Java risky in Cloud serverless",      "replacement": "Custom Routine",           "effort": 8},
    "tJavaRow":      {"reason": "Inline Java risky in Cloud serverless",      "replacement": "Custom Routine",           "effort": 8},
    "tBeanShell":    {"reason": "BeanShell deprecated; blocked in Cloud",     "replacement": "tJavaRow",                 "effort": 6},
    "tGroovy":       {"reason": "Groovy runtime unavailable in Cloud",        "replacement": "tJavaRow",                 "effort": 6},
    "tPythonRow":    {"reason": "Python runtime unavailable in Cloud",        "replacement": "tJavaRow or REST service", "effort": 6},
    "tRubyRow":      {"reason": "Ruby runtime unavailable in Cloud",          "replacement": "tJavaRow or REST service", "effort": 6},
    "tESBConsumer":  {"reason": "ESB runtime not available in Cloud",         "replacement": "tRESTClient",              "effort": 8},
    "tJDBCInput":    {"reason": "Custom JDBC driver JARs blocked in Cloud",   "replacement": "Named cloud connector",    "effort": 6},
    "tJDBCOutput":   {"reason": "Custom JDBC driver JARs blocked in Cloud",   "replacement": "Named cloud connector",    "effort": 6},
    "tJDBCRow":      {"reason": "Custom JDBC driver JARs blocked in Cloud",   "replacement": "Named cloud connector",    "effort": 6},
    "tJDBCConnection": {"reason": "Custom JDBC driver JARs blocked in Cloud", "replacement": "Named cloud connector",    "effort": 6},
}

# Components that require review / manual adjustment
_SOFT_BLOCKERS: Dict[str, Dict[str, Any]] = {
    "tBeanInput":   {"reason": "Bean components may need refactor for T8 class-loading", "replacement": "tJavaRow",      "effort": 4},
    "tBeanOutput":  {"reason": "Bean components may need refactor for T8 class-loading", "replacement": "tJavaRow",      "effort": 4},
    "tSoap":        {"reason": "SOAP API changed in T8 — parameter review required",     "replacement": "tSOAP",         "effort": 3},
    "tWebService":  {"reason": "tWebService replaced by tRESTClient / tSOAP in T8",      "replacement": "tRESTClient",   "effort": 4},
    "tFileArchive": {"reason": "Deprecated in Talend 7; verify T8 support",              "replacement": "tFileUnarchive","effort": 2},
    "tMysqlBulkExec": {"reason": "Vendor-specific bulk; verify driver availability",     "replacement": "tDBOutput",     "effort": 3},
    "tRunJob":      {"reason": "Remote job orchestration may need reconfiguration",      "replacement": "",              "effort": 2},
    "tHiveInput":   {"reason": "Hive connectivity changed in T8 — revalidate connection","replacement": "",              "effort": 4},
    "tHiveOutput":  {"reason": "Hive connectivity changed in T8 — revalidate connection","replacement": "",              "effort": 4},
    "tHiveRow":     {"reason": "Hive connectivity changed in T8 — revalidate connection","replacement": "",              "effort": 4},
}

_SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

_CATEGORY_SEVERITY = {
    "hard_blocker":   "CRITICAL",
    "cloud_blocker":  "HIGH",
    "soft_blocker":   "MEDIUM",
}


def _load_version_unsupported(source_version: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """Merge version-matrix removed_components + version_compatibility into hard blockers."""
    extra: Dict[str, Dict[str, Any]] = {}

    # version_matrix removed_components (all upgrade paths)
    for _key, rules in VERSION_UPGRADE_MATRIX.items():
        for ct in rules.get("removed_components", []):
            if ct not in _HARD_BLOCKERS:
                extra[ct] = {
                    "reason": f"Removed per version upgrade matrix ({_key})",
                    "replacement": "",
                    "effort": 8,
                }

    # version_compatibility unsupported_components for source version
    if source_version and source_version in VERSION_COMPATIBILITY:
        for ct in VERSION_COMPATIBILITY[source_version].get("unsupported_components", []):
            if ct not in _HARD_BLOCKERS and ct not in extra:
                extra[ct] = {
                    "reason": f"Unsupported from {source_version}",
                    "replacement": "",
                    "effort": 8,
                }
    return extra


# ---------------------------------------------------------------------------
# UnsupportedMigrationComponentsAnalyzer
# ---------------------------------------------------------------------------

class UnsupportedMigrationComponentsAnalyzer:
    """
    Detect Talend components that cannot be migrated as-is to Talend 8 / Cloud.

    Usage
    -----
    analyzer = UnsupportedMigrationComponentsAnalyzer()
    report   = analyzer.analyze(all_jobs)

    # With source version for version-specific detection:
    report   = analyzer.analyze(all_jobs, source_version="Talend 6")
    """

    def analyze(
        self,
        all_jobs: Sequence[Dict[str, Any]],
        source_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan all_jobs for unsupported migration components.

        Parameters
        ----------
        all_jobs       : TMA standard job list (entries with 'job_data' key).
        source_version : Optional version string ("Talend 6", "Talend 7") for
                         version-specific unsupported component detection.

        Returns
        -------
        Structured report dict (see module docstring).
        """
        # Merge version-specific hard blockers into the master catalog
        version_extra = _load_version_unsupported(source_version)
        hard_catalog = {**_HARD_BLOCKERS, **version_extra}

        # Accumulators: category -> component_type -> {count, jobs}
        buckets: Dict[str, Dict[str, Dict[str, Any]]] = {
            "hard_blocker":  defaultdict(lambda: {"count": 0, "jobs": set()}),
            "cloud_blocker": defaultdict(lambda: {"count": 0, "jobs": set()}),
            "soft_blocker":  defaultdict(lambda: {"count": 0, "jobs": set()}),
        }

        per_job: Dict[str, Dict[str, List]] = defaultdict(
            lambda: {"hard_blockers": [], "cloud_blockers": [], "soft_blockers": []}
        )

        for job in all_jobs:
            job_data = job.get("job_data", job)
            job_name = job_data.get("job_name", "Unknown")
            components = job_data.get("components", [])

            type_counts: Dict[str, int] = defaultdict(int)
            for comp in components:
                ct = comp.get("component_type", "") if isinstance(comp, dict) else str(comp)
                if ct:
                    type_counts[ct] += 1

            for ct, n in type_counts.items():
                if ct in hard_catalog:
                    buckets["hard_blocker"][ct]["count"] += n
                    buckets["hard_blocker"][ct]["jobs"].add(job_name)
                    per_job[job_name]["hard_blockers"].append(
                        {"component": ct, "count": n, **hard_catalog[ct]}
                    )

                if ct in _CLOUD_BLOCKERS:
                    buckets["cloud_blocker"][ct]["count"] += n
                    buckets["cloud_blocker"][ct]["jobs"].add(job_name)
                    per_job[job_name]["cloud_blockers"].append(
                        {"component": ct, "count": n, **_CLOUD_BLOCKERS[ct]}
                    )

                # Soft blockers only if not already a hard/cloud blocker
                if ct in _SOFT_BLOCKERS and ct not in hard_catalog and ct not in _CLOUD_BLOCKERS:
                    buckets["soft_blocker"][ct]["count"] += n
                    buckets["soft_blocker"][ct]["jobs"].add(job_name)
                    per_job[job_name]["soft_blockers"].append(
                        {"component": ct, "count": n, **_SOFT_BLOCKERS[ct]}
                    )

        # ── Build per-category lists ─────────────────────────────────────
        def _build_list(catalog: Dict, bucket: Dict) -> List[Dict[str, Any]]:
            rows = []
            for ct, data in bucket.items():
                meta = catalog.get(ct, {})
                rows.append({
                    "component": ct,
                    "usage_count": data["count"],
                    "jobs_impacted": sorted(data["jobs"]),
                    "reason": meta.get("reason", ""),
                    "replacement": meta.get("replacement", ""),
                    "effort_hours": data["count"] * meta.get("effort", 4),
                })
            rows.sort(key=lambda r: -r["usage_count"])
            return rows

        hard_list  = _build_list(hard_catalog, buckets["hard_blocker"])
        cloud_list = _build_list(_CLOUD_BLOCKERS, buckets["cloud_blocker"])
        soft_list  = _build_list(_SOFT_BLOCKERS, buckets["soft_blocker"])

        # ── All unsupported flat list ────────────────────────────────────
        seen: set = set()
        all_unsupported: List[Dict[str, Any]] = []

        def _add_flat(rows: List, category: str, severity: str) -> None:
            for r in rows:
                ct = r["component"]
                if ct not in seen:
                    seen.add(ct)
                    all_unsupported.append({
                        "component": ct,
                        "category": category,
                        "severity": severity,
                        "usage_count": r["usage_count"],
                        "jobs_impacted": r["jobs_impacted"],
                        "reason": r["reason"],
                        "replacement": r["replacement"],
                        "effort_hours": r["effort_hours"],
                    })

        _add_flat(hard_list,  "hard_blocker",  "CRITICAL")
        _add_flat(cloud_list, "cloud_blocker",  "HIGH")
        _add_flat(soft_list,  "soft_blocker",   "MEDIUM")

        all_unsupported.sort(
            key=lambda r: (-_SEVERITY_RANK.get(r["severity"], 0), -r["usage_count"])
        )

        # ── Summary ──────────────────────────────────────────────────────
        total_instances = sum(r["usage_count"] for r in all_unsupported)
        all_jobs_impacted = {j for r in all_unsupported for j in r["jobs_impacted"]}

        if hard_list:
            severity = "CRITICAL"
        elif cloud_list:
            severity = "HIGH"
        elif soft_list:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        per_job_list = [
            {"job_name": jn, **data}
            for jn, data in sorted(per_job.items())
        ]

        return {
            "summary": {
                "total_unsupported_types": len(seen),
                "total_instances": total_instances,
                "total_jobs_impacted": len(all_jobs_impacted),
                "hard_blocker_count": len(hard_list),
                "cloud_blocker_count": len(cloud_list),
                "soft_blocker_count": len(soft_list),
                "migration_blocked": len(hard_list) > 0,
                "severity": severity,
            },
            "hard_blockers": hard_list,
            "cloud_blockers": cloud_list,
            "soft_blockers": soft_list,
            "per_job": per_job_list,
            "all_unsupported": all_unsupported,
        }
