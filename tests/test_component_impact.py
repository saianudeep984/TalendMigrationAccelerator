from app.impact_analysis.component_impact_analyzer import ComponentImpactAnalyzer
from app.impact_analysis.usage_heatmap import ComponentUsageIntelligence


def test_component_dependencies_and_cross_job_impact():
    jobs = [{"job_data": {"job_name": "Parent", "components": [
        {"component_type": "tFileInputDelimited", "unique_name": "in"},
        {"component_type": "tMap", "unique_name": "map"}],
        "connections": [{"source": "in", "target": "map"}]}, "dependencies": {"child_jobs": ["Child"]}},
        {"job_data": {"job_name": "Child", "components": [{"component_type": "tLogRow", "unique_name": "log"}]}}]
    result = ComponentImpactAnalyzer().analyze(jobs)
    mapping = next(x for x in result["components"] if x["unique_name"] == "map")
    assert mapping["upstream_components"] == ["in"]
    assert mapping["affected_jobs"] == ["Child", "Parent"]
    assert mapping["impact"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_usage_frequency_and_risk_rankings():
    jobs = [{"job_data": {"job_name": "A", "components": [{"component_type": "tMap"}, {"component_type": "tSystem"}]}},
            {"job_data": {"job_name": "B", "components": [{"component_type": "tMap"}]}}]
    result = ComponentUsageIntelligence().analyze(jobs)
    assert result["by_frequency"][0]["component"] == "tMap"
    assert result["by_frequency"][0]["count"] == 2
    assert result["by_risk"][0]["risk_score"] >= result["by_risk"][-1]["risk_score"]
