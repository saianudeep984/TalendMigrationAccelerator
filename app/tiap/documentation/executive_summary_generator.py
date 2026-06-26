from typing import Any, Dict, Sequence

from app.tiap.documentation.export_utils import export_document, write_executive_summary_pdf
from app.analyzers.readiness_scorer import RepositoryScoring


class ExecutiveSummaryGenerator:
    def _build_metrics(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None, effort: Dict[str, Any] = None) -> Dict[str, Any]:
        scoring = RepositoryScoring().score(all_jobs, repository_path)
        high_risk = sum(
            1 for job in all_jobs for risk in job.get("enterprise_risk_report", [])
            if risk.get("risk") in ("HIGH", "CRITICAL")
        )
        total_components = sum(len(job.get("job_data", {}).get("components", [])) for job in all_jobs)

        complexity_breakdown: Dict[str, int] = {}
        cloud_breakdown: Dict[str, int] = {}
        risk_breakdown: Dict[str, int] = {}
        for job in all_jobs:
            complexity = job.get("estimation", {}).get("complexity", "UNKNOWN")
            complexity_breakdown[complexity] = complexity_breakdown.get(complexity, 0) + 1

            cloud = job.get("cloud_readiness", {}).get("readiness", "UNKNOWN")
            cloud_breakdown[cloud] = cloud_breakdown.get(cloud, 0) + 1

            for risk in job.get("enterprise_risk_report", []):
                severity = risk.get("risk", "UNKNOWN")
                if severity in ("HIGH", "CRITICAL"):
                    component = risk.get("component") or severity
                    risk_breakdown[component] = risk_breakdown.get(component, 0) + 1

        estimated_weeks = effort.get("estimated_weeks", "Not estimated") if effort else "Not estimated"
        return {
            "scores": scoring,
            "portfolio": {
                "total_jobs": len(all_jobs),
                "total_components": total_components,
                "high_risk": high_risk,
                "estimated_weeks": estimated_weeks,
                "auto_pct": effort.get("auto_pct", 0) if effort else 0,
            },
            "complexity_breakdown": complexity_breakdown,
            "cloud_breakdown": cloud_breakdown,
            "risk_breakdown": risk_breakdown,
            "narrative": (
                f"The repository is at {scoring['migration_readiness_score']}% migration readiness "
                f"and {scoring['cloud_readiness_score']}% cloud readiness across {len(all_jobs)} jobs. "
                f"{high_risk} high or critical risk signals require leadership visibility before execution."
            ),
        }

    def generate(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None, effort: Dict[str, Any] = None) -> str:
        metrics = self._build_metrics(all_jobs, repository_path, effort)
        scoring = metrics["scores"]
        portfolio = metrics["portfolio"]
        lines = [
            "# Executive Summary",
            "",
            f"- Total Jobs: {portfolio['total_jobs']}",
            f"- Total Components: {portfolio['total_components']}",
            f"- Migration Readiness: {scoring['migration_readiness_score']}%",
            f"- Cloud Readiness: {scoring['cloud_readiness_score']}%",
            f"- Repository Complexity: {scoring['repository_complexity_score']}%",
            f"- Documentation Readiness: {scoring['documentation_readiness_score']}%",
            f"- Testing Readiness: {scoring['testing_readiness_score']}%",
            f"- High/Critical Risks: {portfolio['high_risk']}",
            f"- Effort: {portfolio['estimated_weeks']} weeks",
            "",
            "## Summary",
            "The repository has been assessed for migration readiness, cloud suitability, documentation coverage, testing readiness, and technical complexity.",
            "",
            "## Executive Narrative",
            metrics["narrative"],
        ]
        return "\n".join(lines)

    def export(self, all_jobs, output_dir, repository_path=None, effort=None):
        markdown = self.generate(all_jobs, repository_path, effort)
        paths = export_document(output_dir, "executive_summary", "Executive Summary", markdown)
        metrics = self._build_metrics(all_jobs, repository_path, effort)
        metrics["markdown"] = markdown
        write_executive_summary_pdf(paths["pdf"], metrics)
        return paths
