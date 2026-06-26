"""
Readiness regression suite (F2.6).
Locks the canonical MigrationReadinessScoreCalculator's numeric output
and the legacy calculate_readiness_score() shim's parity with it, so any
future change to scoring logic surfaces as a failing test here.
"""

from app.analyzers.migration_readiness_score import calculate_migration_readiness_score
from app.analyzers.readiness_scorer import calculate_readiness_score


def _job(name, readiness="HIGH", child_jobs=0, components=None, risk_report=None):
    return {
        "job_data": {"job_name": name, "components": components or [{"component_type": "tLogRow"}]},
        "cloud_readiness": {"readiness": readiness},
        "estimation": {"child_job_count": child_jobs},
        "enterprise_risk_report": risk_report or [],
    }


# Golden fixtures, locked expected values.
_GOLDEN_GREEN = [_job("g1"), _job("g2")]
_GOLDEN_AMBER = [_job("a1", readiness="MEDIUM", child_jobs=8)]
_GOLDEN_RED = [_job("r1", readiness="LOW", child_jobs=30, risk_report=[{"risk": "CRITICAL"}])]


def test_golden_green_overall_score_locked():
    r = calculate_migration_readiness_score(_GOLDEN_GREEN, {"impacted_jobs": 0}, [])
    assert r.overall_score == 100
    assert r.overall_rag == "GREEN"
    assert r.status == "READY"


def test_golden_amber_overall_score_locked():
    r = calculate_migration_readiness_score(
        _GOLDEN_AMBER, {"impacted_jobs": 0}, [{"count": 1, "impacted_jobs": ["a1"]}]
    )
    assert r.overall_score == 62
    assert r.overall_rag == "AMBER"


def test_golden_red_overall_score_locked():
    r = calculate_migration_readiness_score(
        _GOLDEN_RED, {"impacted_jobs": 1}, [{"count": 1, "impacted_jobs": ["r1"]}]
    )
    assert r.overall_score == 21
    assert r.overall_rag == "RED"
    assert r.status == "HIGH REMEDIATION REQUIRED"


def test_zero_total_components_does_not_divide_by_zero():
    r = calculate_migration_readiness_score([_job("z", components=[])], {"impacted_jobs": 0}, [])
    assert r.component_compatibility_score == 100


def test_all_dimensions_present_and_ordered():
    r = calculate_migration_readiness_score(_GOLDEN_GREEN, {"impacted_jobs": 0}, [])
    labels = [d["dimension"] for d in r.dimensions]
    assert labels == [
        "Component Compatibility",
        "Deprecated Component Risk",
        "Custom Component Risk",
        "Cloud Readiness",
        "Dependency Complexity",
        "Analysis Coverage",
        "Risk Findings",
    ]


def test_overall_score_matches_manual_weighted_sum():
    weights = {"cloud_readiness": 0.3, "dependency_complexity": 0.05}
    r = calculate_migration_readiness_score(_GOLDEN_AMBER, {"impacted_jobs": 0}, [], weights=weights)
    manual = int(sum(d["score"] * d["weight"] for d in r.dimensions))
    assert r.overall_score == manual


# --- Single-engine guarantee (F2.5): legacy shim must stay derived from,
# and numerically consistent with, the canonical engine. ---

def test_legacy_shim_overall_matches_canonical_rag():
    canonical = calculate_migration_readiness_score(_GOLDEN_AMBER, {"impacted_jobs": 0},
                                                      [{"count": 1, "impacted_jobs": ["a1"]}])
    legacy = calculate_readiness_score(_GOLDEN_AMBER, {"impacted_jobs": 0},
                                        [{"count": 1, "impacted_jobs": ["a1"]}])
    assert legacy["overall"] == canonical.overall_rag
    assert legacy["status"] == canonical.status


def test_legacy_shim_dimension_rags_match_canonical_subset():
    canonical = calculate_migration_readiness_score(_GOLDEN_RED, {"impacted_jobs": 1},
                                                      [{"count": 1, "impacted_jobs": ["r1"]}])
    legacy = calculate_readiness_score(_GOLDEN_RED, {"impacted_jobs": 1},
                                        [{"count": 1, "impacted_jobs": ["r1"]}])
    by_label = {d["dimension"]: d["rag"] for d in canonical.dimensions}
    assert legacy["component_compatibility"] == by_label["Component Compatibility"]
    assert legacy["deprecated_component_risk"] == by_label["Deprecated Component Risk"]
    assert legacy["custom_component_risk"] == by_label["Custom Component Risk"]
    assert legacy["cloud_readiness"] == by_label["Cloud Readiness"]
    assert legacy["dependency_complexity"] == by_label["Dependency Complexity"]


def test_legacy_shim_empty_jobs_no_data():
    assert calculate_readiness_score([], {}, []) == {"overall": "RED", "status": "NO DATA"}


def test_legacy_shim_breakdown_has_five_legacy_dimensions():
    legacy = calculate_readiness_score(_GOLDEN_GREEN, {"impacted_jobs": 0}, [])
    assert len(legacy["breakdown"]) == 5
    assert {b["dimension"] for b in legacy["breakdown"]} == {
        "Component Compatibility", "Deprecated Component Risk", "Custom Component Risk",
        "Cloud Readiness", "Dependency Complexity",
    }
