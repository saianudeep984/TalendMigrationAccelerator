from typing import Any, Dict, Sequence

from app.analyzers.readiness_scorer import MigrationReadinessAnalyzer
from app.tiap.governance.compliance_assessor import ComplianceAssessor
from app.tiap.refactoring.technical_debt_detector import TechnicalDebtDetector
from app.tiap.testing.regression_suite_builder import RegressionSuiteBuilder


class ExecutiveMetrics:
    def calculate(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None) -> Dict[str, Any]:
        assessment = MigrationReadinessAnalyzer().analyze(all_jobs, repository_path)
        testing = RegressionSuiteBuilder().build(all_jobs)
        governance = ComplianceAssessor().assess(all_jobs)
        debt = TechnicalDebtDetector().analyze(all_jobs)
        effort = assessment["effort_estimation"]
        return {
            "total_jobs": len(all_jobs),
            "migration_readiness": assessment["migration_readiness_percent"],
            "cloud_readiness": assessment["cloud_readiness_percent"],
            "documentation_readiness": assessment["documentation_readiness_percent"],
            "testing_readiness": testing["testing_readiness_score"],
            "technical_debt": debt["debt_score"],
            "pii_risk": governance["pii_detection"]["pii_risk_score"],
            "migration_effort": effort,
            "sizing_category": assessment["migration_sizing_category"],
        }
