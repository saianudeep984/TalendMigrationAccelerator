from app.lineage.advanced_lineage_engine import AdvancedLineageEngine
from app.lineage.transformation_intelligence import TransformationIntelligence


MAPPINGS = {
    "Extract": [{"source_table": "raw", "source_column": "id", "target_table": "shared", "target_column": "id", "rule_type": "direct"}],
    "Load": [{"source_table": "shared", "source_column": "id", "target_table": "mart", "target_column": "customer_id", "expression": "row.id", "rule_type": "expression"}],
}


def test_cross_job_source_to_target_lineage():
    jobs = [{"job_data": {"job_name": "Extract", "components": []}}, {"job_data": {"job_name": "Load", "components": []}}]
    graph = AdvancedLineageEngine().build(jobs, MAPPINGS)
    traced = AdvancedLineageEngine.trace(graph, "Extract:raw.id")
    assert "Load:mart.customer_id" in traced
    assert any(e["type"] == "cross_job" for e in graph["edges"])


def test_transformation_extraction_and_visualization():
    result = TransformationIntelligence().extract(
        [{"source_table": "a", "source_column": "amount", "target_table": "b", "target_column": "total", "expression": "row.amount.sum()"}],
        [{"table": "lookup", "join_type": "LEFT_OUTER_JOIN"}], [], "Job")
    assert result["counts"]["aggregation"] == 1
    assert result["counts"]["join"] == 1
    assert "flowchart LR" in result["visualization"]
