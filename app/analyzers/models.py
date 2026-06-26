"""
Data models for unsupported-component analysis results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CompatibilityStatus(str, Enum):
    """Enumerated compatibility outcomes for an upgrade path."""

    COMPATIBLE = "Compatible"
    CONDITIONAL = "Conditional"
    NOT_COMPATIBLE = "NotCompatible"


@dataclass
class ReplacementRecommendation:
    """Structured recommendation for replacing an unsupported component."""

    component: str
    replacement_component: Optional[str] = None
    auto_fixable: bool = False
    risk: str = "MEDIUM"
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "replacementComponent": self.replacement_component,
            "autoFixable": self.auto_fixable,
            "risk": self.risk,
            "rationale": self.rationale,
        }

@dataclass
class RemediationRecommendation:
    """Actionable remediation step for an unsupported component."""

    component: str
    category: str
    action: str
    replacement_component: Optional[str] = None
    auto_fixable: bool = False
    effort_hours: int = 0
    risk: str = "MEDIUM"

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "category": self.category,
            "action": self.action,
            "replacementComponent": self.replacement_component,
            "autoFixable": self.auto_fixable,
            "effortHours": self.effort_hours,
            "risk": self.risk,
        }


@dataclass
class UpgradeWarning:
    """Non-blocking warning surfaced during an upgrade-path analysis."""

    component: str
    category: str
    message: str
    severity: str = "MEDIUM"

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "category": self.category,
            "message": self.message,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UpgradeWarning":
        return cls(
            component=data.get("component"),
            category=data.get("category"),
            message=data.get("message"),
            severity=data.get("severity", "MEDIUM"),
        )


@dataclass
class UpgradePathResult:
    """Structured result of an UpgradePathAnalyzer path/job analysis."""

    source_version: str
    target_version: str
    target_versions: List[str] = field(default_factory=list)
    compatibility_status: str = CompatibilityStatus.NOT_COMPATIBLE.value
    migration_path: List[str] = field(default_factory=list)
    hops: List[str] = field(default_factory=list)
    supported: bool = False
    renamed_components: Dict[str, str] = field(default_factory=dict)
    removed_components: List[str] = field(default_factory=list)
    parameter_changes: Dict[str, dict] = field(default_factory=dict)
    new_required_parameters: Dict[str, list] = field(default_factory=dict)
    component_findings: List[dict] = field(default_factory=list)
    warnings: List[dict] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sourceVersion": self.source_version,
            "targetVersion": self.target_version,
            "targetVersions": self.target_versions,
            "compatibilityStatus": self.compatibility_status,
            "migrationPath": self.migration_path,
            "hops": self.hops,
            "supported": self.supported,
            "renamedComponents": self.renamed_components,
            "removedComponents": self.removed_components,
            "parameterChanges": self.parameter_changes,
            "newRequiredParameters": self.new_required_parameters,
            "componentFindings": self.component_findings,
            "warnings": self.warnings,
            "blockers": self.blockers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UpgradePathResult":
        return cls(
            source_version=data.get("sourceVersion"),
            target_version=data.get("targetVersion"),
            target_versions=data.get("targetVersions", []),
            compatibility_status=data.get("compatibilityStatus", CompatibilityStatus.NOT_COMPATIBLE.value),
            migration_path=data.get("migrationPath", []),
            hops=data.get("hops", []),
            supported=data.get("supported", False),
            renamed_components=data.get("renamedComponents", {}),
            removed_components=data.get("removedComponents", []),
            parameter_changes=data.get("parameterChanges", {}),
            new_required_parameters=data.get("newRequiredParameters", {}),
            component_findings=data.get("componentFindings", []),
            warnings=data.get("warnings", []),
            blockers=data.get("blockers", []),
        )


@dataclass
class RepositoryOverview:
    """Aggregated repository-level metrics bound to RepositoryOverviewCard."""

    total_jobs: int = 0
    total_joblets: int = 0
    total_routines: int = 0
    total_components: int = 0
    complexity_score: int = 0
    migration_readiness_score: int = 0
    cloud_readiness_score: int = 0
    testing_readiness_score: int = 0
    repository_type: str = "Unknown"
    source_version: str = "UNKNOWN"
    enterprise_features: List[str] = field(default_factory=list)
    target_versions: List[str] = field(default_factory=list)
    migration_risk: str = "LOW"
    upgrade_path_summary: str = ""

    def to_dict(self) -> dict:
        return {
            "totalJobs": self.total_jobs,
            "totalJoblets": self.total_joblets,
            "totalRoutines": self.total_routines,
            "totalComponents": self.total_components,
            "complexityScore": self.complexity_score,
            "migrationReadinessScore": self.migration_readiness_score,
            "cloudReadinessScore": self.cloud_readiness_score,
            "testingReadinessScore": self.testing_readiness_score,
            "repositoryType": self.repository_type,
            "sourceVersion": self.source_version,
            "enterpriseFeatures": self.enterprise_features,
            "targetVersions": self.target_versions,
            "migrationRisk": self.migration_risk,
            "upgradePathSummary": self.upgrade_path_summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RepositoryOverview":
        return cls(
            total_jobs=data.get("totalJobs", 0),
            total_joblets=data.get("totalJoblets", 0),
            total_routines=data.get("totalRoutines", 0),
            total_components=data.get("totalComponents", 0),
            complexity_score=data.get("complexityScore", 0),
            migration_readiness_score=data.get("migrationReadinessScore", 0),
            cloud_readiness_score=data.get("cloudReadinessScore", 0),
            testing_readiness_score=data.get("testingReadinessScore", 0),
            repository_type=data.get("repositoryType", "Unknown"),
            source_version=data.get("sourceVersion", "UNKNOWN"),
            enterprise_features=data.get("enterpriseFeatures", []),
            target_versions=data.get("targetVersions", []),
            migration_risk=data.get("migrationRisk", "LOW"),
            upgrade_path_summary=data.get("upgradePathSummary", ""),
        )

    @classmethod
    def from_inventory_and_scoring(
        cls,
        inventory: dict,
        scoring: dict,
        repository_type_info: dict = None,
        enterprise_features_info: dict = None,
        upgrade_path_info: dict = None,
    ) -> "RepositoryOverview":
        kpis = inventory.get("kpis", {})
        repository_type_info = repository_type_info or {}
        enterprise_features_info = enterprise_features_info or {}
        upgrade_path_info = upgrade_path_info or {}
        return cls(
            total_jobs=kpis.get("total_jobs", 0),
            total_joblets=kpis.get("total_joblets", 0),
            total_routines=kpis.get("total_routines", 0),
            total_components=kpis.get("total_components", 0),
            complexity_score=scoring.get("repository_complexity_score", 0),
            migration_readiness_score=scoring.get("migration_readiness_score", 0),
            cloud_readiness_score=scoring.get("cloud_readiness_score", 0),
            testing_readiness_score=scoring.get("testing_readiness_score", 0),
            repository_type=repository_type_info.get("type", "Unknown"),
            source_version=repository_type_info.get("source_version", "UNKNOWN"),
            enterprise_features=enterprise_features_info.get("summary", []),
            target_versions=upgrade_path_info.get("targetVersions", []),
            migration_risk=upgrade_path_info.get("migrationRisk", "LOW"),
            upgrade_path_summary=upgrade_path_info.get("summary", ""),
        )


@dataclass
class ExecutiveDashboard:
    """Aggregated portfolio-level KPIs bound to the Executive Dashboard page
    (ExecutiveDashboardCard / render_executive_dashboard_page).
    """

    total_jobs: int = 0
    analyzed_jobs: int = 0
    ready_jobs: int = 0
    total_components: int = 0
    cloud_readiness_status: str = "RED"
    automation_pct: int = 0
    manual_pct: int = 0
    estimated_hours: int = 0
    estimated_weeks: Any = "—"
    estimated_days: Any = "—"
    high_risk_count: int = 0
    warning_jobs: int = 0
    failed_jobs: int = 0
    risk_label: str = "LOW"
    complexity_breakdown: Dict[str, int] = field(default_factory=dict)
    total_routines: Any = "—"
    total_joblets: Any = "—"

    def to_dict(self) -> dict:
        return {
            "totalJobs": self.total_jobs,
            "analyzedJobs": self.analyzed_jobs,
            "readyJobs": self.ready_jobs,
            "totalComponents": self.total_components,
            "cloudReadinessStatus": self.cloud_readiness_status,
            "automationPct": self.automation_pct,
            "manualPct": self.manual_pct,
            "estimatedHours": self.estimated_hours,
            "estimatedWeeks": self.estimated_weeks,
            "estimatedDays": self.estimated_days,
            "highRiskCount": self.high_risk_count,
            "warningJobs": self.warning_jobs,
            "failedJobs": self.failed_jobs,
            "riskLabel": self.risk_label,
            "complexityBreakdown": self.complexity_breakdown,
            "totalRoutines": self.total_routines,
            "totalJoblets": self.total_joblets,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutiveDashboard":
        return cls(
            total_jobs=data.get("totalJobs", 0),
            analyzed_jobs=data.get("analyzedJobs", 0),
            ready_jobs=data.get("readyJobs", 0),
            total_components=data.get("totalComponents", 0),
            cloud_readiness_status=data.get("cloudReadinessStatus", "RED"),
            automation_pct=data.get("automationPct", 0),
            manual_pct=data.get("manualPct", 0),
            estimated_hours=data.get("estimatedHours", 0),
            estimated_weeks=data.get("estimatedWeeks", "—"),
            estimated_days=data.get("estimatedDays", "—"),
            high_risk_count=data.get("highRiskCount", 0),
            warning_jobs=data.get("warningJobs", 0),
            failed_jobs=data.get("failedJobs", 0),
            risk_label=data.get("riskLabel", "LOW"),
            complexity_breakdown=data.get("complexityBreakdown", {}),
            total_routines=data.get("totalRoutines", "—"),
            total_joblets=data.get("totalJoblets", "—"),
        )

    @classmethod
    def from_session_data(
        cls,
        all_jobs: list,
        readiness: dict = None,
        effort: dict = None,
        routines: dict = None,
        joblets: dict = None,
    ) -> "ExecutiveDashboard":
        """Build an ExecutiveDashboard model from the same session-state
        sources used by the legacy inline dashboard (last_analysis_jobs,
        readiness_score, effort_estimate, routine_analysis, joblet_analysis).
        """
        readiness = readiness or {}
        effort = effort or {}
        routines = routines or {}
        joblets = joblets or {}

        all_jobs = all_jobs or []
        total_jobs = len(all_jobs)
        total_components = sum(
            len(j.get("job_data", j).get("components", [])) for j in all_jobs
        )
        overall = readiness.get("overall", "RED")
        auto_pct = effort.get("auto_pct", 0) if effort else 0
        manual_pct = effort.get("manual_pct", 0) if effort else 0
        est_hours = effort.get("estimated_hours", 0) if effort else 0
        est_weeks = effort.get("estimated_weeks", "—") if effort else "—"
        est_days = effort.get("estimated_days", "—") if effort else "—"
        high_risk = sum(
            1
            for j in all_jobs
            for r in j.get("enterprise_risk_report", [])
            if r.get("risk") in ("HIGH", "CRITICAL")
        )
        risk_label = "HIGH" if high_risk else ("MEDIUM" if auto_pct < 60 else "LOW")
        by_complexity = effort.get("by_complexity", {}) if effort else {}

        analyzed_jobs = sum(1 for j in all_jobs if j.get("estimation"))

        from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag

        def _job_rag(j):
            cr = j.get("cloud_readiness", {}) or {}
            if "readiness" in cr:
                # calculate_cloud_readiness() output: HIGH=ready, MEDIUM=warning, LOW=blocked.
                # Map on the readiness tier, not the (inverted) rag color field.
                tier = cr.get("readiness")
                return {"HIGH": "GREEN", "MEDIUM": "AMBER", "LOW": "RED"}.get(tier, "AMBER")
            if "score" in cr:
                return _score_to_rag(cr.get("score", 0))
            if cr.get("rag") in ("RED", "AMBER", "GREEN"):
                return cr["rag"]
            return "AMBER"

        ready_jobs = sum(1 for j in all_jobs if _job_rag(j) == "GREEN")
        warning_jobs = sum(1 for j in all_jobs if _job_rag(j) == "AMBER")
        failed_jobs = sum(1 for j in all_jobs if _job_rag(j) == "RED")

        return cls(
            total_jobs=total_jobs,
            analyzed_jobs=analyzed_jobs,
            ready_jobs=ready_jobs,
            total_components=total_components,
            cloud_readiness_status=overall,
            automation_pct=auto_pct,
            manual_pct=manual_pct,
            estimated_hours=est_hours,
            estimated_weeks=est_weeks,
            estimated_days=est_days,
            high_risk_count=high_risk,
            warning_jobs=warning_jobs,
            failed_jobs=failed_jobs,
            risk_label=risk_label,
            complexity_breakdown=by_complexity,
            total_routines=routines.get("total_routines", "—") if routines else "—",
            total_joblets=joblets.get("total_joblets", "—") if joblets else "—",
        )


@dataclass
class MigrationReadinessScore:
    """Portfolio-level migration readiness score with weighted dimension
    breakdown. Produced by MigrationReadinessScoreCalculator
    (app.analyzers.migration_readiness_score) from the same per-job
    session-state shape used by ExecutiveDashboard / calculate_readiness_score.
    """

    overall_score: int = 0
    overall_rag: str = "RED"
    status: str = "NO DATA"
    component_compatibility_score: int = 0
    deprecated_component_risk_score: int = 0
    custom_component_risk_score: int = 0
    cloud_readiness_score: int = 0
    dependency_complexity_score: int = 0
    analysis_coverage_score: int = 0
    risk_findings_score: int = 0
    weights: Dict[str, float] = field(default_factory=dict)
    dimensions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overallScore": self.overall_score,
            "overallRag": self.overall_rag,
            "status": self.status,
            "componentCompatibilityScore": self.component_compatibility_score,
            "deprecatedComponentRiskScore": self.deprecated_component_risk_score,
            "customComponentRiskScore": self.custom_component_risk_score,
            "cloudReadinessScore": self.cloud_readiness_score,
            "dependencyComplexityScore": self.dependency_complexity_score,
            "analysisCoverageScore": self.analysis_coverage_score,
            "riskFindingsScore": self.risk_findings_score,
            "weights": self.weights,
            "dimensions": self.dimensions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MigrationReadinessScore":
        return cls(
            overall_score=data.get("overallScore", 0),
            overall_rag=data.get("overallRag", "RED"),
            status=data.get("status", "NO DATA"),
            component_compatibility_score=data.get("componentCompatibilityScore", 0),
            deprecated_component_risk_score=data.get("deprecatedComponentRiskScore", 0),
            custom_component_risk_score=data.get("customComponentRiskScore", 0),
            cloud_readiness_score=data.get("cloudReadinessScore", 0),
            dependency_complexity_score=data.get("dependencyComplexityScore", 0),
            analysis_coverage_score=data.get("analysisCoverageScore", 0),
            risk_findings_score=data.get("riskFindingsScore", 0),
            weights=data.get("weights", {}),
            dimensions=data.get("dimensions", []),
        )
