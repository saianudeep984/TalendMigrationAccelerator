from app.migration_intelligence.effort_estimator import MigrationEffortEstimator


def test_effort_has_job_and_project_breakdown():
    complexity = {"jobs": [{"job_name": "A", "complexity": "HIGH", "factors": {"components": 8, "custom_java": 1}}]}
    result = MigrationEffortEstimator().estimate(complexity, {"edges": []})
    assert result["estimated_hours"] > 32
    assert result["recommended_team_size"] >= 1
    assert result["job_breakdown"][0]["build_hours"] > 0
    assert result["project_breakdown"]["test_hours"] > 0
