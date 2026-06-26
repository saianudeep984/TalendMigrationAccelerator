from app.impact_analysis.deprecated_component_analyzer import DeprecatedComponentAnalyzer


def test_talend_7_to_8_findings_replacements_and_effort():
    jobs = [{"job_data": {"job_name": "Legacy", "components": [
        {"component_type": "tMysqlInput"}, {"component_type": "tUnknownLegacy"}]}}]
    result = DeprecatedComponentAnalyzer().analyze(jobs)
    findings = {x["component"]: x for x in result["findings"]}
    assert findings["tMysqlInput"]["status"] == "DEPRECATED"
    assert findings["tMysqlInput"]["replacement"] == "tDBInput"
    assert findings["tUnknownLegacy"]["status"] == "UNSUPPORTED"
    assert result["summary"]["remediation_hours"] > 0
