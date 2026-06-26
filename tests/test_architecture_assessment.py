from app.architecture.architecture_assessor import ArchitectureAssessmentEngine
from app.architecture.anti_pattern_detector import ArchitectureAntiPatternDetector
from app.ui.architecture_intelligence_dashboard import (
    architecture_autofix_report_markdown,
    build_architecture_autofix_intelligence,
    export_architecture_autofix,
)


def sample_jobs():
    return [
        {"job_data": {"job_name": "LoadA", "components": [
            {"component_type": "tFileInputDelimited", "parameters": {"filename": "C:\\data\\in.csv"}},
            {"component_type": "tMysqlInput", "parameters": {"password": "secret"}},
            {"component_type": "tMap", "parameters": {"expression": "x;" * 40}},
        ]}, "dependencies": {"contexts": ["Default"], "metadata_connections": ["mysql"]}},
        {"job_data": {"job_name": "LoadB", "components": [
            {"component_type": "tFileInputDelimited"},
            {"component_type": "tMysqlInput"},
            {"component_type": "tMap"},
        ]}, "dependencies": {"contexts": ["Default"], "metadata_connections": ["mysql"]}},
    ]


def test_architecture_assessment_scorecard_and_dashboard_exports():
    data = build_architecture_autofix_intelligence(sample_jobs(), {"score": 75})
    scorecard = data["architecture"]["scorecard"]
    assert scorecard["architecture_quality_score"] >= 0
    assert "technical_debt" in data["architecture"]
    assert data["autofix"]["summary"]["total"] >= 1
    report = architecture_autofix_report_markdown(data)
    for section in ("Architecture Scorecard", "Technical Debt", "Anti-Patterns", "Best Practices", "Auto-Fix Recommendations", "Confidence Scores"):
        assert section in report
    assert export_architecture_autofix(data, "html").startswith(b"<!doctype html>")
    assert export_architecture_autofix(data, "pdf").startswith(b"%PDF")
    assert export_architecture_autofix(data, "json").startswith(b"{")
    assert export_architecture_autofix(data, "xlsx").startswith(b"PK")


def test_anti_pattern_detector_finds_required_patterns():
    result = ArchitectureAntiPatternDetector().detect(sample_jobs())
    assert result["summary"]["hardcoded_paths"] >= 1
    assert result["summary"]["hardcoded_credentials"] >= 1
    assert result["summary"]["missing_error_handling"] >= 1
    assert result["summary"]["duplicate_job_logic"] >= 1
    assert result["summary"]["excessive_tmap_complexity"] >= 1


def test_architecture_engine_uses_readiness_signal():
    result = ArchitectureAssessmentEngine().analyze(sample_jobs(), {"score": 88})
    assert result["scorecard"]["migration_readiness_score"] == 88
    assert result["architecture_maturity_score"] == result["scorecard"]["overall_architecture_maturity_score"]

