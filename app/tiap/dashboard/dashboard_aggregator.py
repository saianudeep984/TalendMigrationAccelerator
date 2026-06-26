import os
from typing import Any, Dict, Sequence

from app.tiap.dashboard.executive_metrics import ExecutiveMetrics
from app.tiap.dashboard.portfolio_analyzer import PortfolioAnalyzer
from app.tiap.dashboard.trend_analyzer import TrendAnalyzer
from app.tiap.models.repository import write_json


class DashboardAggregator:
    def aggregate(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None, output_dir: str = None, history=None) -> Dict[str, Any]:
        metrics = ExecutiveMetrics().calculate(all_jobs, repository_path)
        portfolio = PortfolioAnalyzer().analyze(all_jobs)
        trends = TrendAnalyzer().analyze(metrics, history)
        charts = {
            "migration_progress": portfolio["migration_progress"],
            "risk_distribution": {
                "technical_debt": metrics["technical_debt"],
                "pii_risk": metrics["pii_risk"],
                "inverse_readiness_risk": 100 - metrics["migration_readiness"],
            },
            "cloud_readiness": portfolio["portfolio_view"]["jobs_by_cloud_readiness"],
            "documentation_coverage": metrics["documentation_readiness"],
            "testing_coverage": metrics["testing_readiness"],
            "portfolio_view": portfolio["portfolio_view"],
        }
        result = {"repository_portfolio_metrics": metrics, "charts": charts, "trend_analysis": trends, **portfolio}
        if output_dir:
            write_json(os.path.join(output_dir, "executive_dashboard.json"), result)
        return result
