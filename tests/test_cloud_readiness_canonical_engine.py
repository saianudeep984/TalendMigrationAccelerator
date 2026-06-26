from app.analyzers.cloud_readiness import (
    CloudReadinessAnalyzer,
    CloudReadinessEngine,
    calculate_cloud_readiness,
)
from app.tiap.assessment.cloud_readiness import CloudReadinessAnalyzer as TiapAlias
from app.analyzers.readiness_scorer import CloudReadinessAnalyzer as ScorerAlias


def test_aliases_point_to_canonical_class():
    assert TiapAlias is CloudReadinessAnalyzer
    assert ScorerAlias is CloudReadinessAnalyzer


def test_rag_mapping_not_inverted():
    job_critical = {"components": [{"component_type": "tSystem"}]}
    job_clean = {"components": [{"component_type": "tMap"}]}
    crit = calculate_cloud_readiness(job_critical)
    clean = calculate_cloud_readiness(job_clean)
    assert crit["readiness"] == "LOW" and crit["rag"] == "RED"
    assert clean["readiness"] == "HIGH" and clean["rag"] == "GREEN"


def test_unified_engine_facade():
    engine = CloudReadinessEngine()
    job_result = engine.analyze_job({"components": [{"component_type": "tMap"}]})
    assert job_result["rag"] == "GREEN"

    repo_result = engine.analyze_repository([
        {"job_data": {"job_name": "J1", "components": [{"component_type": "tSystem"}]}}
    ])
    assert repo_result["cloud_blockers"][0]["component"] == "tSystem"
