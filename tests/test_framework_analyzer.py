from app.framework_analyzer.framework_best_practice import FrameworkBestPracticeAnalyzer
from app.framework_analyzer.framework_detector import FrameworkDetectionEngine


def test_framework_detection_and_maturity():
    jobs = [{"job_data": {"job_name": "j1", "components": [{"component_type": c} for c in ["tLogCatcher", "tDie", "tContextLoad", "tRunJob"]]}}]
    detected = FrameworkDetectionEngine().detect(jobs)
    assert detected["logging_framework"]["detected"]
    result = FrameworkBestPracticeAnalyzer().analyze(jobs)
    assert result["framework_maturity"]["framework_maturity_score"] >= 0
    assert "recommendations" in result
