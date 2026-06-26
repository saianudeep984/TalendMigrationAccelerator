from __future__ import annotations
from app.architecture.architecture_assessor import ArchitectureAssessmentEngine
from .upgrade_inventory import UpgradeInventoryEngine
from .compatibility_matrix import CompatibilityMatrixEngine
from .breaking_change_analyzer import BreakingChangeAnalyzer
from .deprecated_component_analyzer import UpgradeDeprecatedComponentAnalyzer
from .impact_assessment import UpgradeImpactAssessmentEngine
from .autofix_opportunity import AutoFixOpportunityAnalyzer
from .remediation_analyzer import ManualRemediationAnalyzer
from .effort_estimator import UpgradeEffortEstimator
from .readiness_engine import UpgradeReadinessEngine


class UpgradeRecommendationEngine:
    def recommend(self, jobs, source_version="Talend 7.x", target_version="Talend 8.x"):
        inv = UpgradeInventoryEngine().analyze(jobs, source_version, target_version)
        comp = CompatibilityMatrixEngine().classify_project(jobs, source_version, target_version)
        breaking = BreakingChangeAnalyzer().analyze(jobs, source_version, target_version)
        dep = UpgradeDeprecatedComponentAnalyzer().analyze(jobs)
        arch = ArchitectureAssessmentEngine().analyze(jobs)
        auto = AutoFixOpportunityAnalyzer().analyze(jobs, arch)
        manual = ManualRemediationAnalyzer().analyze(breaking, dep, auto)
        impact = UpgradeImpactAssessmentEngine().assess(jobs, comp, breaking, dep)
        effort = UpgradeEffortEstimator().estimate(jobs, impact, manual)
        ready = UpgradeReadinessEngine().score(jobs, comp, auto, manual)
        score = ready["upgrade_readiness_percent"]
        rec = "Proceed" if score >= 85 and impact["classification"] == "LOW" else "Proceed With Fixes" if score >= 65 else "Partial Refactor" if score >= 40 else "Full Refactor"
        return {"inventory": inv, "compatibility": comp, "breaking_changes": breaking, "deprecated_components": dep,
                "architecture": arch, "autofix_opportunity": auto, "manual_remediation": manual, "impact_assessment": impact,
                "effort_estimate": effort, "readiness": ready, "recommendation": {"decision": rec, "rationale": f"Readiness {score}%, impact {impact['classification']}.", "next_actions": ["Resolve critical findings", "Apply auto-fixes", "Execute migration waves", "Validate regression suite"]}}
