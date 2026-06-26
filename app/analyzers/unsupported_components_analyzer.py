"""
UnsupportedComponentsAnalyzer

Service class that detects Talend components that cannot migrate as-is to
Talend 8 / Talend Cloud and produces a structured remediation report.

Categories detected
-------------------
- tJava*         : tJava, tJavaRow, tJavaFlex — inline Java code
- tSystem        : tSystem, tLibraryLoad, tBeanShell, tGroovy, tPythonRow, tRubyRow
- Custom JDBC    : tJDBC* components requiring third-party driver JARs
- Custom/Unknown : components not present in the TALEND8_KNOWN_COMPONENTS catalog
- Deprecated     : components with known replacements in Talend 8

Returns
-------
{
  "summary": {
      "total_unsupported_types": int,
      "total_instances": int,
      "total_jobs_impacted": int,
      "total_effort_hours": int,
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
  },
  "categories": {
      "<category>": {
          "count": int,
          "job_count": int,
          "jobs": [str, ...],
          "effort_hours": int,
          "instances": [...],
          "meta": { icon, severity, description, recommendation, color,
                    effort_hours_per_instance }
      }, ...
  },
  "per_job": [
      { "job_name": str, "issues": [{ "category": str, "component_type": str,
                                       "count": int }] }
  ],
  "all_unsupported": [
      { "component": str, "category": str, "usage_count": int,
        "jobs_impacted": [str], "effort_hours": int,
        "severity": str, "recommendation": str }
  ]
}
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence

from app.config.component_rules import (
    DEPRECATED_COMPONENT_MAP,
    TALEND8_KNOWN_COMPONENTS,
)
from app.tiap.models.repository import iter_job_data
from app.analyzers.models import ReplacementRecommendation, RemediationRecommendation

# ---------------------------------------------------------------------------
# Detection sets
# ---------------------------------------------------------------------------

_JAVA_COMPONENTS = {"tJava", "tJavaRow", "tJavaFlex"}

_SYSTEM_COMPONENTS = {
    "tSystem", "tLibraryLoad", "tBeanShell", "tGroovy",
    "tPythonRow", "tRubyRow",
}

_CUSTOM_JDBC_COMPONENTS = {
    "tJDBCInput", "tJDBCOutput", "tJDBCRow",
    "tJDBCConnection", "tJDBCCommit", "tJDBCClose", "tJDBCRollback",
}

# Standard components that are safe for Talend 8 / Cloud
_STANDARD_COMPONENTS = set(TALEND8_KNOWN_COMPONENTS)

# ---------------------------------------------------------------------------
# Category metadata
# ---------------------------------------------------------------------------

_CATEGORY_META: Dict[str, Dict[str, Any]] = {
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
        "description": "OS command execution is unsupported in the Talend Cloud serverless runtime.",
        "recommendation": "Replace with a REST API call, cloud function, or managed service trigger.",
        "color": "#be123c",
    },
    "Custom JDBC": {
        "icon": "🔌",
        "severity": "HIGH",
        "effort_hours_per_instance": 6,
        "description": "Generic JDBC connectors require custom driver JARs not available in cloud runtime.",
        "recommendation": "Replace with a named cloud-native connector (tSnowflakeInput, tBigQueryInput, etc.).",
        "color": "#0369a1",
    },
    "Deprecated": {
        "icon": "⚠️",
        "severity": "MEDIUM",
        "effort_hours_per_instance": 3,
        "description": "Components with known replacements in Talend 8; may cause import failures.",
        "recommendation": "Replace with the recommended Talend 8 equivalent before migration.",
        "color": "#d97706",
    },
    "Custom/Unknown": {
        "icon": "🔧",
        "severity": "MEDIUM",
        "effort_hours_per_instance": 4,
        "description": "Components not found in the Talend 8 standard catalog — possibly third-party or internal.",
        "recommendation": "Validate availability in target runtime; package or replace as needed.",
        "color": "#6d28d9",
    },
}


def _category_severity_rank(sev: str) -> int:
    return {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(sev, 0)


# ---------------------------------------------------------------------------
# UnsupportedComponentsAnalyzer
# ---------------------------------------------------------------------------

class UnsupportedComponentsAnalyzer:
    """
    Analyse a Talend job list for components that cannot migrate as-is.

    Usage
    -----
    analyzer = UnsupportedComponentsAnalyzer()
    report   = analyzer.analyze(all_jobs)
    """

    def analyze(
        self,
        all_jobs: Sequence[Dict[str, Any]],
        routine_analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Scan all_jobs for unsupported components.

        Parameters
        ----------
        all_jobs         : Standard TMA job list (entries with 'job_data' key).
        routine_analysis : Optional result of routine_analyzer; enriches
                           Custom/Unknown detection with routine-level risk.

        Returns
        -------
        Structured report dict (see module docstring).
        """
        cats: Dict[str, Dict[str, Any]] = {
            key: {"count": 0, "jobs": set(), "instances": []}
            for key in _CATEGORY_META
        }

        # component_type -> {count, jobs}
        type_registry: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "jobs": set(), "category": "Custom/Unknown"}
        )

        per_job: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for job in all_jobs:
            job_data = job.get("job_data", job)
            job_name = job_data.get("job_name", "Unknown")
            components = job_data.get("components", [])

            type_counts: Dict[str, int] = defaultdict(int)
            for comp in components:
                ct = comp.get("component_type", "") if isinstance(comp, dict) else str(comp)
                if ct:
                    type_counts[ct] += 1

            # ── tJava* ──────────────────────────────────────────────────
            java_hits = {ct: n for ct, n in type_counts.items() if ct in _JAVA_COMPONENTS}
            if java_hits:
                total = sum(java_hits.values())
                cats["tJava*"]["count"] += total
                cats["tJava*"]["jobs"].add(job_name)
                cats["tJava*"]["instances"].append(
                    {"job": job_name, "count": total, "breakdown": java_hits}
                )
                for ct, n in java_hits.items():
                    per_job[job_name].append(
                        {"category": "tJava*", "component_type": ct, "count": n}
                    )
                    self._register(type_registry, ct, n, job_name, "tJava*")

            # ── tSystem ─────────────────────────────────────────────────
            sys_hits = {ct: n for ct, n in type_counts.items() if ct in _SYSTEM_COMPONENTS}
            if sys_hits:
                total = sum(sys_hits.values())
                cats["tSystem"]["count"] += total
                cats["tSystem"]["jobs"].add(job_name)
                cats["tSystem"]["instances"].append(
                    {"job": job_name, "count": total, "breakdown": sys_hits}
                )
                for ct, n in sys_hits.items():
                    per_job[job_name].append(
                        {"category": "tSystem", "component_type": ct, "count": n}
                    )
                    self._register(type_registry, ct, n, job_name, "tSystem")

            # ── Custom JDBC ──────────────────────────────────────────────
            jdbc_hits = {ct: n for ct, n in type_counts.items() if ct in _CUSTOM_JDBC_COMPONENTS}
            if jdbc_hits:
                total = sum(jdbc_hits.values())
                cats["Custom JDBC"]["count"] += total
                cats["Custom JDBC"]["jobs"].add(job_name)
                cats["Custom JDBC"]["instances"].append(
                    {"job": job_name, "count": total, "breakdown": jdbc_hits}
                )
                for ct, n in jdbc_hits.items():
                    per_job[job_name].append(
                        {"category": "Custom JDBC", "component_type": ct, "count": n}
                    )
                    self._register(type_registry, ct, n, job_name, "Custom JDBC")

            # ── Deprecated ──────────────────────────────────────────────
            dep_hits = {
                ct: n for ct, n in type_counts.items()
                if ct in DEPRECATED_COMPONENT_MAP
                and ct not in _JAVA_COMPONENTS
                and ct not in _SYSTEM_COMPONENTS
                and ct not in _CUSTOM_JDBC_COMPONENTS
            }
            if dep_hits:
                total = sum(dep_hits.values())
                cats["Deprecated"]["count"] += total
                cats["Deprecated"]["jobs"].add(job_name)
                cats["Deprecated"]["instances"].append(
                    {"job": job_name, "count": total, "breakdown": dep_hits}
                )
                for ct, n in dep_hits.items():
                    per_job[job_name].append(
                        {"category": "Deprecated", "component_type": ct, "count": n}
                    )
                    self._register(type_registry, ct, n, job_name, "Deprecated")

            # ── Custom / Unknown (not in any previous bucket, not standard) ──
            already_handled = (
                set(_JAVA_COMPONENTS)
                | set(_SYSTEM_COMPONENTS)
                | set(_CUSTOM_JDBC_COMPONENTS)
                | set(DEPRECATED_COMPONENT_MAP)
                | _STANDARD_COMPONENTS
            )
            custom_hits = {
                ct: n for ct, n in type_counts.items()
                if ct not in already_handled
            }
            if custom_hits:
                total = sum(custom_hits.values())
                cats["Custom/Unknown"]["count"] += total
                cats["Custom/Unknown"]["jobs"].add(job_name)
                cats["Custom/Unknown"]["instances"].append(
                    {"job": job_name, "count": total, "breakdown": custom_hits}
                )
                for ct, n in custom_hits.items():
                    per_job[job_name].append(
                        {"category": "Custom/Unknown", "component_type": ct, "count": n}
                    )
                    self._register(type_registry, ct, n, job_name, "Custom/Unknown")

        # ── Routine-level enrichment ─────────────────────────────────────
        if routine_analysis:
            for r in routine_analysis.get("routines", []):
                jobs_using = r.get("jobs_using", [])
                count = max(1, r.get("job_count", len(jobs_using)))
                cats["Custom/Unknown"]["count"] += count
                cats["Custom/Unknown"]["jobs"].update(jobs_using)
                cats["Custom/Unknown"]["instances"].append({
                    "routine": r.get("name", "—"),
                    "risk": r.get("risk_level", "LOW"),
                    "jobs": jobs_using,
                    "count": count,
                    "risks": r.get("risks", []),
                })

        # ── Serialise ────────────────────────────────────────────────────
        for key, cat in cats.items():
            meta = _CATEGORY_META[key]
            cat["jobs"] = sorted(cat["jobs"])
            cat["job_count"] = len(cat["jobs"])
            cat["effort_hours"] = cat["count"] * meta["effort_hours_per_instance"]
            cat["meta"] = meta

        # ── Summary ──────────────────────────────────────────────────────
        total_instances = sum(v["count"] for v in cats.values())
        total_jobs = len({j for v in cats.values() for j in v["jobs"]})
        total_effort = sum(v["effort_hours"] for v in cats.values())

        # Overall severity = highest active category
        active_severities = [
            _CATEGORY_META[k]["severity"]
            for k, v in cats.items()
            if v["count"] > 0
        ]
        if active_severities:
            severity = max(active_severities, key=_category_severity_rank)
        else:
            severity = "LOW"

        # ── all_unsupported flat list ─────────────────────────────────────
        all_unsupported = self._build_flat_list(type_registry)
        remediation_actions = self._build_remediation_actions(type_registry)

        per_job_list = [
            {"job_name": jn, "issues": issues}
            for jn, issues in sorted(per_job.items())
        ]

        return {
            "summary": {
                "total_unsupported_types": len(type_registry),
                "total_instances": total_instances,
                "total_jobs_impacted": total_jobs,
                "total_effort_hours": total_effort,
                "severity": severity,
            },
            "categories": cats,
            "per_job": per_job_list,
            "all_unsupported": all_unsupported,
            "remediation_actions": remediation_actions,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _register(
        registry: Dict,
        component_type: str,
        count: int,
        job_name: str,
        category: str,
    ) -> None:
        entry = registry[component_type]
        is_first = entry["count"] == 0
        entry["count"] += count
        entry["jobs"].add(job_name)
        # keep the highest-priority category if seen in multiple
        existing = entry.get("category", "Custom/Unknown")
        if is_first or _category_severity_rank(
            _CATEGORY_META.get(category, {}).get("severity", "LOW")
        ) > _category_severity_rank(
            _CATEGORY_META.get(existing, {}).get("severity", "LOW")
        ):
            entry["category"] = category

    @staticmethod
    def _build_flat_list(
        registry: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rows = []
        for ct, entry in registry.items():
            category = entry.get("category", "Custom/Unknown")
            meta = _CATEGORY_META.get(category, _CATEGORY_META["Custom/Unknown"])
            effort = entry["count"] * meta["effort_hours_per_instance"]
            replacement = DEPRECATED_COMPONENT_MAP.get(ct, {}).get("replacement", "")
            rec = (
                f"Replace with {replacement}"
                if replacement
                else meta["recommendation"]
            )
            dep_info = DEPRECATED_COMPONENT_MAP.get(ct, {})
            replacement_rec = ReplacementRecommendation(
                component=ct,
                replacement_component=replacement or None,
                auto_fixable=dep_info.get("auto_fix", False),
                risk=dep_info.get("risk", meta["severity"]),
                rationale=rec,
            )
            rows.append({
                "component": ct,
                "category": category,
                "usage_count": entry["count"],
                "jobs_impacted": sorted(entry["jobs"]),
                "effort_hours": effort,
                "severity": meta["severity"],
                "recommendation": rec,
                "replacementComponent": replacement_rec.replacement_component,
            })
        rows.sort(key=lambda r: (-_category_severity_rank(r["severity"]), -r["usage_count"]))
        return rows

    @staticmethod
    def _build_remediation_actions(
        registry: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Generate a concrete remediation action per unsupported component type."""
        actions = []
        for ct, entry in registry.items():
            category = entry.get("category", "Custom/Unknown")
            meta = _CATEGORY_META.get(category, _CATEGORY_META["Custom/Unknown"])
            dep_info = DEPRECATED_COMPONENT_MAP.get(ct, {})
            replacement = dep_info.get("replacement", "")

            if replacement:
                action_text = f"Replace {ct} with {replacement} and revalidate the job."
            else:
                action_text = f"{meta['recommendation']} ({ct})"

            remediation = RemediationRecommendation(
                component=ct,
                category=category,
                action=action_text,
                replacement_component=replacement or None,
                auto_fixable=dep_info.get("auto_fix", False),
                effort_hours=entry["count"] * meta["effort_hours_per_instance"],
                risk=dep_info.get("risk", meta["severity"]),
            )
            actions.append(remediation.to_dict())

        actions.sort(key=lambda a: (-_category_severity_rank(a["risk"]), a["component"]))
        return actions
