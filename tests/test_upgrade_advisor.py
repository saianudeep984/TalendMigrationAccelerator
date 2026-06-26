from app.upgrade_advisor.recommendation_engine import UpgradeRecommendationEngine
from app.upgrade_advisor.compatibility_matrix import CompatibilityMatrixEngine


def _job(name, comps):
    return {"job_data": {"job_name": name, "components": [{"component_type": c} for c in comps]}}


def test_upgrade_advisor_end_to_end():
    jobs = [_job("load_customer", ["tMysqlInput", "tMap", "tSystem", "tJavaRow"])]
    result = UpgradeRecommendationEngine().recommend(jobs, "Talend 7.x", "Talend 8.x")
    assert result["inventory"]["project_inventory"]["jobs"] == 1
    assert result["compatibility"]["summary"]["Deprecated"] >= 1
    assert result["breaking_changes"]["summary"]["critical"] >= 1
    assert result["impact_assessment"]["upgrade_impact_score"] >= 0
    assert result["readiness"]["upgrade_readiness_percent"] >= 0
    assert result["recommendation"]["decision"] in {"Proceed", "Proceed With Fixes", "Partial Refactor", "Full Refactor"}


def test_compatibility_matrix_classifies_components():
    result = CompatibilityMatrixEngine().classify_project([_job("j", ["tFooUnknown", "tMap"])])
    assert result["summary"]["Unsupported"] == 1
