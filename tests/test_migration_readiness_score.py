from app.analyzers.migration_readiness_score import (
    MigrationReadinessScoreCalculator,
    calculate_migration_readiness_score,
)
from app.analyzers.models import MigrationReadinessScore


def _job(name, readiness="HIGH", child_jobs=0, components=None):
    return {
        "job_data": {
            "job_name": name,
            "components": components or [{"component_type": "tLogRow"}],
        },
        "cloud_readiness": {"readiness": readiness},
        "estimation": {"child_job_count": child_jobs},
    }


def test_calculate_returns_migration_readiness_score_model():
    result = calculate_migration_readiness_score([_job("a")], {"impacted_jobs": 0}, [])
    assert isinstance(result, MigrationReadinessScore)
    assert result.overall_rag in {"GREEN", "AMBER", "RED"}
    assert len(result.dimensions) == 7


def test_empty_jobs_returns_no_data():
    result = MigrationReadinessScoreCalculator().calculate([], {}, [])
    assert result.overall_rag == "RED"
    assert result.status == "NO DATA"
    assert result.dimensions == []


def test_green_amber_red_bands():
    green = calculate_migration_readiness_score([_job("green")], {"impacted_jobs": 0}, [])
    amber = calculate_migration_readiness_score(
        [_job("amber", readiness="MEDIUM", child_jobs=8)],
        {"impacted_jobs": 0},
        [{"count": 1, "impacted_jobs": ["amber"]}],
    )
    red = calculate_migration_readiness_score(
        [_job("red", readiness="LOW", child_jobs=30)],
        {"impacted_jobs": 1},
        [{"count": 1, "impacted_jobs": ["red"]}],
    )

    assert green.overall_rag == "GREEN"
    assert amber.overall_rag == "AMBER"
    assert red.overall_rag == "RED"


def test_to_dict_from_dict_round_trip():
    result = calculate_migration_readiness_score([_job("a")], {"impacted_jobs": 0}, [])
    data = result.to_dict()
    restored = MigrationReadinessScore.from_dict(data)
    assert restored.overall_score == result.overall_score
    assert restored.overall_rag == result.overall_rag
    assert restored.dimensions == result.dimensions
    assert restored.weights == result.weights


def test_custom_weights_are_applied():
    result = calculate_migration_readiness_score(
        [_job("a")], {"impacted_jobs": 0}, [], weights={"cloud_readiness": 0.5}
    )
    assert result.weights["cloud_readiness"] == 0.5


def test_dimension_entries_have_expected_keys():
    result = calculate_migration_readiness_score([_job("a")], {"impacted_jobs": 0}, [])
    for dim in result.dimensions:
        assert {"dimension", "score", "rag", "weight", "detail"} <= dim.keys()


def test_analysis_coverage_reflects_analyzed_jobs():
    jobs = [_job("analyzed")]
    jobs[0]["estimation"] = {"child_job_count": 0}
    unanalyzed = _job("unanalyzed")
    unanalyzed["estimation"] = {}
    jobs.append(unanalyzed)

    result = calculate_migration_readiness_score(jobs, {"impacted_jobs": 0}, [])
    assert result.analysis_coverage_score == 50


def test_risk_findings_reflects_enterprise_risk_report():
    job_clean = _job("clean")
    job_clean["enterprise_risk_report"] = []
    job_risky = _job("risky")
    job_risky["enterprise_risk_report"] = [{"risk": "HIGH"}, {"risk": "CRITICAL"}]

    result = calculate_migration_readiness_score([job_clean, job_risky], {"impacted_jobs": 0}, [])
    assert result.risk_findings_score < 100
    risk_dim = next(d for d in result.dimensions if d["dimension"] == "Risk Findings")
    assert "2 HIGH/CRITICAL findings" in risk_dim["detail"]
