"""
TMA Migration Assessment
Generates: Cloud Readiness, Unsupported Components, Migration Risks, Effort Estimation, Recommendations
Reuses: cloud_readiness (analyzers + tiap), unsupported_component_analyzer, risk_analyzer, effort_estimator
"""
from __future__ import annotations
from typing import Any

from app.analyzers.cloud_readiness import calculate_cloud_readiness
from app.analyzers.unsupported_component_analyzer import analyze_unsupported_components
from app.analyzers.version_upgrade_analyzer import UpgradePathAnalyzer
from app.analyzers.version_compatibility_engine import VersionCompatibilityEngine
from app.analyzers.models import UpgradePathResult, CompatibilityStatus
from app.risk_engine.risk_analyzer import RiskAnalyzer
from app.tiap.assessment.complexity_analyzer import ComplexityAnalyzer


# ── Cloud Readiness ───────────────────────────────────────────────────────────

def get_cloud_readiness(job_data: dict) -> dict:
    """Reuse existing assessment engine (app.analyzers.cloud_readiness)."""
    return calculate_cloud_readiness(job_data)


# ── Unsupported Components ────────────────────────────────────────────────────

def get_unsupported_components(job_data: dict) -> list[dict]:
    """Reuse analyze_unsupported_components, wrapping the single job as all_jobs."""
    wrapped = [{"job_data": job_data}]
    report = analyze_unsupported_components(wrapped)
    out = []
    for cat_name, cat in report.get("categories", {}).items():
        if cat["count"] == 0:
            continue
        out.append({
            "category": cat_name,
            "count": cat["count"],
            "jobs_impacted": sorted(cat["jobs"]) if isinstance(cat["jobs"], set) else cat["jobs"],
            "impact_level": _impact_for_category(cat_name),
        })
    return out


def _impact_for_category(cat_name: str) -> str:
    return {
        "tJava*": "HIGH",
        "tSystem": "CRITICAL",
        "Custom Routines": "MEDIUM",
        "Custom JDBC": "HIGH",
    }.get(cat_name, "MEDIUM")


# ── Migration Risks ────────────────────────────────────────────────────────────

def get_migration_risks(job_data: dict) -> list[dict]:
    """Reuse RiskAnalyzer; normalize CRITICAL into the High bucket for the 3-tier view."""
    risks = RiskAnalyzer().analyze(job_data)
    for r in risks:
        r["bucket"] = "High" if r["risk"] in ("CRITICAL", "HIGH") else (
            "Medium" if r["risk"] == "MEDIUM" else "Low"
        )
    return risks


# ── Effort Estimation ─────────────────────────────────────────────────────────

def get_effort_estimation(job_data: dict) -> dict:
    """Job-level effort estimate, derived from ComplexityAnalyzer (single-job wrap)."""
    wrapped = [{"job_data": job_data, "complexity": {}}]
    complexity = ComplexityAnalyzer().analyze(wrapped)
    score = complexity["repository_complexity_score"]
    hours = round(4 + min(32, score / 8) + len(job_data.get("components", [])) * 0.5, 1)

    drivers = []
    n_components = len(job_data.get("components", []))
    if n_components > 20:
        drivers.append("High component count")
    if score > 60:
        drivers.append("High structural complexity")
    unsupported = get_unsupported_components(job_data)
    if unsupported:
        drivers.append("Unsupported component remediation")
    if not drivers:
        drivers.append("Standard migration pattern")

    return {
        "estimated_hours": hours,
        "complexity": complexity["sizing_category"],
        "complexity_score": score,
        "effort_drivers": drivers,
    }


# ── Recommendations ────────────────────────────────────────────────────────────

def get_recommendations(job_data: dict) -> list[str]:
    """Reuse assessment results (cloud readiness, unsupported components, risks)."""
    recs = []
    cloud = get_cloud_readiness(job_data)
    if cloud.get("readiness") == "LOW":
        recs.append("Prioritize remediation of cloud blockers before scheduling migration.")

    unsupported = get_unsupported_components(job_data)
    for u in unsupported:
        recs.append(f"Remediate {u['count']} instance(s) of {u['category']} (impact: {u['impact_level']}).")

    risks = get_migration_risks(job_data)
    for r in risks:
        if r["bucket"] == "High":
            recs.append(f"Address {r['component']} risk: {r.get('recommendation', 'review and remediate')}.")

    upgrade_path = get_upgrade_path(job_data)
    for finding in upgrade_path.get("componentFindings", []):
        recs.append(f"Upgrade impact on {finding['component']} ({finding['impact']}): {finding['action']}.")

    if not recs:
        recs.append("No blocking issues detected — job is a strong candidate for direct migration.")

    return recs


# ── Upgrade Path ───────────────────────────────────────────────────────────────

def get_upgrade_path(job_data: dict, source_version: str = None, target_version: str = "Talend 8") -> dict:
    """Reuse UpgradePathAnalyzer to compute hop-by-hop upgrade impact for this job."""
    source_version = source_version or job_data.get("source_version") or job_data.get("talend_version") or "Talend 7"

    result_dict = UpgradePathAnalyzer().analyze_job(job_data, source_version, target_version)

    engine = VersionCompatibilityEngine()
    supported_targets = engine.get_supported_targets(source_version)
    result_dict["targetVersions"] = [t["version"] for t in supported_targets]

    match = next((t for t in supported_targets if t["version"] == target_version), None)
    result_dict["migrationPath"] = match["path"] if match else []

    if not match:
        result_dict["compatibilityStatus"] = CompatibilityStatus.NOT_COMPATIBLE.value
        result_dict.setdefault("blockers", [])
        result_dict["blockers"].append(
            f"{target_version} is not a supported upgrade target from {source_version}."
        )
    elif result_dict.get("componentFindings"):
        result_dict["compatibilityStatus"] = CompatibilityStatus.CONDITIONAL.value
    else:
        result_dict["compatibilityStatus"] = CompatibilityStatus.COMPATIBLE.value

    return UpgradePathResult.from_dict(result_dict).to_dict()


# ── Master Builder ────────────────────────────────────────────────────────────

def build_migration_assessment(job_data: dict, source_version: str = None, target_version: str = "Talend 8") -> dict:
    return {
        "job_name": job_data.get("job_name", "Unknown"),
        "cloud_readiness": get_cloud_readiness(job_data),
        "unsupported_components": get_unsupported_components(job_data),
        "migration_risks": get_migration_risks(job_data),
        "upgrade_path": get_upgrade_path(job_data, source_version, target_version),
        "effort_estimation": get_effort_estimation(job_data),
        "recommendations": get_recommendations(job_data),
    }
