"""Unified F11-F13 impact and lineage intelligence orchestration."""
from app.migration_intelligence.dependency_graph import DependencyGraphEngine
from app.lineage.advanced_lineage_engine import AdvancedLineageEngine
from app.lineage.transformation_intelligence import TransformationIntelligence
from .component_impact_analyzer import ComponentImpactAnalyzer
from .deprecated_component_analyzer import DeprecatedComponentAnalyzer
from .usage_heatmap import ComponentUsageIntelligence
from .business_criticality import BusinessCriticalityScorer


class ImpactLineageIntelligenceEngine:
    def analyze(self, jobs, mappings_by_job=None, repository_metadata=None, migration_intelligence=None, readiness=None):
        dependencies = (migration_intelligence or {}).get("dependency_graph") or DependencyGraphEngine().build(jobs)
        lineage = AdvancedLineageEngine().build(jobs, mappings_by_job, repository_metadata)
        component_impact = ComponentImpactAnalyzer().analyze(jobs, dependencies)
        deprecated = DeprecatedComponentAnalyzer().analyze(jobs)
        usage = ComponentUsageIntelligence().analyze(jobs)
        criticality = BusinessCriticalityScorer().score(lineage)
        transformations = {"transformations": lineage["transformations"]}
        transformations["counts"] = {kind: sum(x["type"] == kind for x in lineage["transformations"])
                                      for kind in ("join", "lookup", "filter", "expression", "aggregation", "mapping")}
        transformations["visualization"] = TransformationIntelligence.visualize(lineage["transformations"])
        return {"component_impact": component_impact, "deprecated_components": deprecated,
                "component_usage": usage, "lineage": lineage, "transformations": transformations,
                "criticality": criticality, "readiness": readiness or {},
                "migration_intelligence": migration_intelligence or {},
                "executive_summary": self._summary(component_impact, deprecated, lineage, criticality)}

    @staticmethod
    def _summary(impact, deprecated, lineage, criticality):
        return (f"Analyzed {len(impact['components'])} component instances and {len(lineage['nodes'])} lineage assets. "
                f"Found {deprecated['summary']['total']} Talend 8 compatibility findings and "
                f"{len(criticality['critical_assets'])} high or critical data assets.")
