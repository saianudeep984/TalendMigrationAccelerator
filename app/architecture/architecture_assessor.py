"""Unified Architecture Intelligence assessment engine."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict

from app.analyzers.migration_readiness_score import calculate_migration_readiness_score
from app.architecture.anti_pattern_detector import ArchitectureAntiPatternDetector, components, ctype, job_data
from app.architecture.architecture_scorecard import ArchitectureScorecard
from app.architecture.best_practice_analyzer import BestPracticeAnalyzer
from app.architecture.technical_debt_engine import TechnicalDebtEngine
from app.migration_intelligence.engine import MigrationIntelligenceEngine


class ArchitectureAssessmentEngine:
    def analyze(self, jobs, readiness=None, migration_intelligence=None, impact_intelligence=None, lineage_service=None) -> Dict[str, Any]:
        jobs = list(jobs or [])
        readiness = readiness or calculate_migration_readiness_score(jobs, {}, []).__dict__
        migration_intelligence = migration_intelligence or MigrationIntelligenceEngine().analyze(jobs, readiness, lineage_service)
        anti = ArchitectureAntiPatternDetector().detect(jobs, migration_intelligence.get("dependency_graph"))
        debt = TechnicalDebtEngine().calculate(anti, migration_intelligence)
        structure = self._structure(jobs, migration_intelligence.get("dependency_graph", {}))
        scorecard = ArchitectureScorecard().build({
            "anti_patterns": anti, "technical_debt": debt, "migration_intelligence": migration_intelligence,
            "readiness": readiness, "structure": structure,
        })
        practices = BestPracticeAnalyzer().analyze(anti, scorecard)
        return {
            "project_structure": structure,
            "framework_usage": self._framework_usage(jobs),
            "metadata_driven_design": {"score": int(structure["metadata_ratio"] * 100), "metadata_assets": structure["metadata_assets"]},
            "reusable_joblets": {"score": int(structure["joblet_ratio"] * 100), "joblets": structure["joblet_assets"]},
            "context_management": {"score": int(structure["context_ratio"] * 100), "contexts": structure["context_assets"]},
            "logging_error_handling": {"score": max(0, 100 - anti["summary"].get("missing_error_handling", 0) * 20)},
            "architecture_maturity_score": scorecard["overall_architecture_maturity_score"],
            "scorecard": scorecard,
            "anti_patterns": anti,
            "best_practices": practices,
            "technical_debt": debt,
            "migration_intelligence": migration_intelligence,
            "impact_intelligence": impact_intelligence or {},
        }

    @staticmethod
    def _structure(jobs, graph):
        jobs = list(jobs or [])
        comp_types = [ctype(c) for j in jobs for c in components(j)]
        joblet_assets = [t for t in comp_types if "Joblet" in t or t.startswith("tJoblet")]
        metadata_assets = graph.get("nodes", [])
        metadata_assets = [n for n in metadata_assets if n.get("type") == "metadata"]
        context_assets = [n for n in graph.get("nodes", []) if n.get("type") == "context"]
        java_count = sum(t in {"tJava", "tJavaRow", "tJavaFlex", "tBeanShell", "tGroovy"} for t in comp_types)
        total = max(1, len(comp_types))
        adjacency = graph.get("adjacency", {})
        deep_penalty = max(0, (max((len(v) for v in adjacency.values()), default=0) - 3) * 8)
        return {
            "job_count": len(jobs), "component_count": len(comp_types), "component_distribution": dict(Counter(comp_types)),
            "metadata_assets": len(metadata_assets), "context_assets": len(context_assets), "joblet_assets": len(joblet_assets),
            "metadata_ratio": min(1.0, len(metadata_assets) / max(1, len(jobs))),
            "context_ratio": min(1.0, len(context_assets) / max(1, len(jobs))),
            "joblet_ratio": min(1.0, len(joblet_assets) / max(1, len(jobs))),
            "inline_java_ratio": java_count / total,
            "deep_chain_penalty": deep_penalty,
        }

    @staticmethod
    def _framework_usage(jobs):
        types = Counter(ctype(c) for j in jobs for c in components(j))
        return {
            "database_components": sum(v for k, v in types.items() if "DB" in k or any(x in k for x in ("Mysql", "Oracle", "MSSql", "JDBC"))),
            "file_components": sum(v for k, v in types.items() if k.startswith("tFile")),
            "cloud_components": sum(v for k, v in types.items() if any(x in k for x in ("S3", "Azure", "GCS", "BigQuery", "Snowflake"))),
            "java_components": sum(v for k, v in types.items() if k.startswith("tJava") or k in {"tBeanShell", "tGroovy"}),
            "logging_components": sum(v for k, v in types.items() if k in {"tLogCatcher", "tStatCatcher", "tFlowMeterCatcher", "tLogRow"}),
        }

