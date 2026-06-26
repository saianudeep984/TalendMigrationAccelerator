from app.autofix.confidence_engine import ConfidenceScoringEngine


def test_confidence_engine_returns_all_dimensions():
    jobs = [{"job_data": {"job_name": "A", "components": [{"component_type": "tMap"}]}, "dependencies": {}}]
    result = ConfidenceScoringEngine().score(
        jobs,
        architecture={"anti_patterns": {"findings": [{}]}},
        autofix={"component_rules": {"findings": [{}]}},
        impact={"lineage": {"edges": [{}, {}]}},
        migration_intelligence={},
        readiness={"score": 80},
    )
    expected = {
        "version_detection_confidence", "readiness_confidence", "complexity_confidence",
        "lineage_confidence", "auto_fix_confidence", "architecture_analysis_confidence",
    }
    assert expected == set(result["scores"])
    assert 0 <= result["overall_confidence"] <= 100

