from app.impact_analysis.business_criticality import BusinessCriticalityScorer
from app.impact_analysis.data_impact_analyzer import DataImpactAnalyzer
from app.lineage.advanced_lineage_engine import AdvancedLineageEngine


def _graph():
    jobs = [{"job_data": {"job_name": "A", "components": []}}, {"job_data": {"job_name": "B", "components": []}}]
    mappings = {"A": [{"source_table": "raw", "source_column": "id", "target_table": "shared", "target_column": "id"}],
                "B": [{"source_table": "shared", "source_column": "id", "target_table": "mart", "target_column": "id"}]}
    return AdvancedLineageEngine().build(jobs, mappings)


def test_data_impact_finds_downstream_jobs_and_targets():
    result = DataImpactAnalyzer().analyze(_graph(), "raw", "id")
    assert result["downstream_jobs"] == ["A", "B"]
    assert "mart.id" in result["affected_targets"]
    assert result["impact_count"] >= 3


def test_business_criticality_scores_columns_and_tables():
    result = BusinessCriticalityScorer().score(_graph())
    assert result["columns"] and result["tables"]
    assert result["columns"][0]["criticality"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert result["columns"][0]["downstream_impact"] > 0
