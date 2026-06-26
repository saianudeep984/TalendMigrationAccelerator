from app.migration_intelligence.complexity_engine import MigrationComplexityEngine


def test_project_and_job_complexity_scores():
    jobs = [{"job_data": {"job_name": "A", "components": [{"component_type": "tMap"}, {"component_type": "tJava"}]},
             "dependencies": {"child_jobs": ["B"], "contexts": ["Default"], "routines": ["Custom.fn"]}},
            {"job_data": {"job_name": "B", "components": [{"component_type": "tLogRow"}]}}]
    result = MigrationComplexityEngine().analyze(jobs)
    assert result["job_count"] == 2
    assert result["score"] > 0
    assert result["jobs"][0]["factors"]["custom_java"] == 1
    assert result["jobs"][0]["complexity"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_empty_project_is_low():
    result = MigrationComplexityEngine().analyze([])
    assert result["score"] == 0 and result["complexity"] == "LOW"
