from collections import defaultdict
from typing import Any, Dict, Sequence

from app.config.component_rules import DEPRECATED_COMPONENT_MAP, TALEND8_KNOWN_COMPONENTS
from app.tiap.models.repository import iter_job_data
from app.analyzers.models import ReplacementRecommendation


NEVER_CUSTOM = {
    "tSendMail",
    "tFixedFlowInput",
    "tJDBCConnection",
    "tJDBCClose",
    "tJDBCCommit",
    "tMSSqlClose",
    "tMSSqlCommit",
    "tTeradataInput",
    "tTeradataClose",
}

# Components that are explicitly non-standard and should be flagged as CUSTOM
# even though their name starts with "t" (which normally lands in UNKNOWN).
KNOWN_CUSTOM_COMPONENTS = {
    "tUnpivotRow",
    "tPivotToColumnsDynamic",
}


STANDARD_COMPONENTS = set(TALEND8_KNOWN_COMPONENTS) | NEVER_CUSTOM
TALEND_CATALOG = {
    "Talend Open Studio": STANDARD_COMPONENTS | {"tMysqlInput", "tMysqlOutput", "tOracleInput"},
    "Talend 6": STANDARD_COMPONENTS | {"tMomInput", "tMomOutput"},
    "Talend 7": STANDARD_COMPONENTS,
    "Talend 8": STANDARD_COMPONENTS,
    "Talend Cloud": STANDARD_COMPONENTS - {"tSystem", "tLibraryLoad"},
}


class ComponentProfiler:
    def classify(self, component_name: str) -> str:
        if not component_name:
            return "UNKNOWN"
        if component_name in DEPRECATED_COMPONENT_MAP:
            return "DEPRECATED"
        if component_name in STANDARD_COMPONENTS:
            return "STANDARD"
        if component_name in KNOWN_CUSTOM_COMPONENTS:
            return "CUSTOM"
        if component_name.startswith(("t", "c")):
            return "UNKNOWN"
        return "CUSTOM"

    def profile(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        usage = defaultdict(lambda: {"count": 0, "jobs": set(), "classification": "UNKNOWN"})
        distribution = {"STANDARD": 0, "DEPRECATED": 0, "CUSTOM": 0, "UNKNOWN": 0}

        for data in iter_job_data(all_jobs):
            job_name = data.get("job_name", "Unknown")
            for component in data.get("components", []):
                if not isinstance(component, dict):
                    continue
                ctype = component.get("component_type", "")
                classification = self.classify(ctype)
                usage[ctype]["count"] += 1
                usage[ctype]["jobs"].add(job_name)
                usage[ctype]["classification"] = classification
                distribution[classification] += 1

        rows = []
        for component, item in usage.items():
            count = item["count"]
            classification = item["classification"]
            risk = "LOW"
            if classification == "CUSTOM":
                risk = "HIGH" if count > 5 else "MEDIUM"
            elif classification in ("DEPRECATED", "UNKNOWN"):
                risk = "MEDIUM"
            rows.append({
                "component": component,
                "classification": classification,
                "usage_count": count,
                "jobs_impacted": sorted(item["jobs"]),
                "risk": risk,
                "recommendation": self._recommendation(component, classification),
                "replacementComponent": self._replacement_recommendation(component, classification).replacement_component,
            })

        rows.sort(key=lambda row: (-row["usage_count"], row["component"]))
        return {
            "catalog_versions": sorted(TALEND_CATALOG),
            "component_usage": rows,
            "component_distribution": distribution,
            "top_components": rows[:20],
            "migration_risk": {
                "high": [r for r in rows if r["risk"] == "HIGH"],
                "medium": [r for r in rows if r["risk"] == "MEDIUM"],
                "low": [r for r in rows if r["risk"] == "LOW"],
            },
            "standard_components": [r for r in rows if r["classification"] == "STANDARD"],
            "deprecated_components": [r for r in rows if r["classification"] == "DEPRECATED"],
            "custom_components": [r for r in rows if r["classification"] == "CUSTOM"],
            "unknown_components": [r for r in rows if r["classification"] == "UNKNOWN"],
            "total_custom": sum(1 for r in rows if r["classification"] == "CUSTOM"),
            "impacted_jobs": len({j for r in rows if r["classification"] in ("CUSTOM", "UNKNOWN") for j in r["jobs_impacted"]}),
        }

    def _recommendation(self, component: str, classification: str) -> str:
        if classification == "DEPRECATED":
            return f"Replace with {DEPRECATED_COMPONENT_MAP[component]['replacement']}"
        if classification == "CUSTOM":
            return "Review custom component implementation and Talend Cloud support"
        if classification == "UNKNOWN":
            return "Validate component availability in target Talend runtime"
        return "Supported standard component"

    def _replacement_recommendation(self, component: str, classification: str) -> ReplacementRecommendation:
        dep_info = DEPRECATED_COMPONENT_MAP.get(component, {})
        return ReplacementRecommendation(
            component=component,
            replacement_component=dep_info.get("replacement") or None,
            auto_fixable=dep_info.get("auto_fix", False),
            risk=dep_info.get("risk", "LOW"),
            rationale=self._recommendation(component, classification),
        )


def profile_components(all_jobs):
    return ComponentProfiler().profile(all_jobs)
