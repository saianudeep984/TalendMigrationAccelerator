"""
MigrationReadinessScoreCalculator
Canonical engine computing a weighted MigrationReadinessScore model from
repository analysis results (all_jobs / custom_analysis / deprecated_rows),
combining component/cloud/dependency dimensions from
calculate_readiness_score() in readiness_scorer.py with analyzed-job
coverage and enterprise risk-finding metrics, and exposing numeric
per-dimension scores alongside RAG bands.
"""

from typing import Any, Dict, List, Sequence

from app.analyzers.models import MigrationReadinessScore
from app.analyzers.readiness_scorer import _READINESS_WEIGHT, _rag

_DEFAULT_WEIGHTS = {
    "component_compatibility": 0.20,
    "deprecated_component_risk": 0.10,
    "custom_component_risk": 0.15,
    "cloud_readiness": 0.20,
    "dependency_complexity": 0.10,
    "analysis_coverage": 0.10,
    "risk_findings": 0.15,
}

# Canonical ordered dimension spec: (key, weight_key, label, score_fn, detail_fn)
# score_fn(ctx) -> int 0..100 ; detail_fn(ctx) -> str
_DIMENSIONS = [
    (
        "component_compatibility", "component_compatibility", "Component Compatibility",
        lambda c: 100 if c["total_components"] == 0 else max(0, 100 - int(c["deprecated_count"] / c["total_components"] * 100)),
        lambda c: f"{c['deprecated_count']} deprecated usages across {c['total_components']} total",
    ),
    (
        "deprecated_component_risk", "deprecated_component_risk", "Deprecated Component Risk",
        lambda c: max(0, 100 - int(c["depr_jobs"] / c["total"] * 60)),
        lambda c: f"{c['depr_jobs']} of {c['total']} jobs have deprecated components",
    ),
    (
        "custom_component_risk", "custom_component_risk", "Custom Component Risk",
        lambda c: max(0, 100 - int(c["custom_jobs"] / c["total"] * 80)),
        lambda c: f"{c['custom_jobs']} jobs use non-standard components",
    ),
    (
        "cloud_readiness", "cloud_readiness", "Cloud Readiness",
        lambda c: int(sum(_READINESS_WEIGHT.get(j.get("cloud_readiness", {}).get("readiness"), 20) for j in c["all_jobs"]) / c["total"]),
        lambda c: "Average cloud readiness rating across all jobs",
    ),
    (
        "dependency_complexity", "dependency_complexity", "Dependency Complexity",
        lambda c: max(0, 100 - min(100, c["total_child"] * 5)),
        lambda c: f"{c['total_child']} total child-job dependencies detected",
    ),
    (
        "analysis_coverage", "analysis_coverage", "Analysis Coverage",
        lambda c: int(c["analyzed_jobs"] / c["total"] * 100),
        lambda c: f"{c['analyzed_jobs']} of {c['total']} jobs analyzed",
    ),
    (
        "risk_findings", "risk_findings", "Risk Findings",
        lambda c: max(0, 100 - min(100, int(c["high_risk_findings"] / c["total"] * 100))),
        lambda c: f"{c['high_risk_findings']} HIGH/CRITICAL findings across {c['total']} jobs",
    ),
]


class MigrationReadinessScoreCalculator:
    """Canonical service that binds repository analysis results to a
    MigrationReadinessScore model."""

    def calculate(
        self,
        all_jobs: Sequence[Dict[str, Any]],
        custom_analysis: Dict[str, Any] = None,
        deprecated_rows: List[Dict[str, Any]] = None,
        weights: Dict[str, float] = None,
    ) -> MigrationReadinessScore:
        all_jobs = all_jobs or []
        custom_analysis = custom_analysis or {}
        deprecated_rows = deprecated_rows or []
        w = {**_DEFAULT_WEIGHTS, **(weights or {})}

        if not all_jobs:
            return MigrationReadinessScore(
                overall_score=0, overall_rag="RED", status="NO DATA",
                weights=w, dimensions=[],
            )

        total = len(all_jobs)
        ctx = {
            "all_jobs": all_jobs,
            "total": total,
            "deprecated_count": sum(r.get("count", 0) for r in deprecated_rows),
            "total_components": sum(len(j.get("job_data", {}).get("components", [])) for j in all_jobs),
            "depr_jobs": len(set(j for r in deprecated_rows for j in r.get("impacted_jobs", []))),
            "custom_jobs": custom_analysis.get("impacted_jobs", 0),
            "total_child": sum(j.get("estimation", {}).get("child_job_count", 0) for j in all_jobs),
            "analyzed_jobs": sum(1 for j in all_jobs if j.get("estimation")),
            "high_risk_findings": sum(
                1 for j in all_jobs for r in j.get("enterprise_risk_report", [])
                if r.get("risk") in ("HIGH", "CRITICAL")
            ),
        }

        scores: Dict[str, int] = {}
        dimensions = []
        for key, wkey, label, score_fn, detail_fn in _DIMENSIONS:
            score = score_fn(ctx)
            scores[key] = score
            dimensions.append({
                "dimension": label, "score": score, "rag": _rag(score),
                "weight": w[wkey], "detail": detail_fn(ctx),
            })

        overall = int(sum(scores[key] * w[wkey] for key, wkey, *_ in _DIMENSIONS))

        if overall >= 80:
            status = "READY"
        elif overall >= 60:
            status = "PARTIAL — REMEDIATION RECOMMENDED"
        else:
            status = "HIGH REMEDIATION REQUIRED"

        return MigrationReadinessScore(
            overall_score=overall,
            overall_rag=_rag(overall),
            status=status,
            component_compatibility_score=scores["component_compatibility"],
            deprecated_component_risk_score=scores["deprecated_component_risk"],
            custom_component_risk_score=scores["custom_component_risk"],
            cloud_readiness_score=scores["cloud_readiness"],
            dependency_complexity_score=scores["dependency_complexity"],
            analysis_coverage_score=scores["analysis_coverage"],
            risk_findings_score=scores["risk_findings"],
            weights=w,
            dimensions=dimensions,
        )


def calculate_migration_readiness_score(
    all_jobs, custom_analysis=None, deprecated_rows=None, weights=None
) -> MigrationReadinessScore:
    """Module-level convenience wrapper around MigrationReadinessScoreCalculator."""
    return MigrationReadinessScoreCalculator().calculate(
        all_jobs, custom_analysis=custom_analysis, deprecated_rows=deprecated_rows, weights=weights
    )
