from app.autofix.autofix_generator import AutoFixGenerator
from app.autofix.autofix_validator import AutoFixValidationFramework
from app.autofix.rule_engine import AutoFixRuleEngine, MigrationRuleRepository


def test_rule_engine_maps_deprecated_components_to_replacements():
    jobs = [{"job_data": {"job_name": "A", "components": [{"component_type": "tMysqlInput"}]}}]
    result = AutoFixRuleEngine().analyze_components(jobs)
    assert result["findings"][0]["replacement"] == "tDBInput"
    assert result["upgrade_recommendations"][0]["target_version"] == "Talend 8.x"


def test_autofix_generator_before_after_and_validation():
    jobs = [{"job_data": {"job_name": "A", "components": [{"component_type": "tSOAP11"}]}}]
    result = AutoFixGenerator().generate(jobs)
    rec = result["recommendations"][0]
    assert rec["before_state"]["component"] == "tSOAP11"
    assert rec["after_state"]["component"] == "tSOAP"
    validation = AutoFixValidationFramework().validate(result)
    assert validation["valid"]


def test_rule_repository_handles_unknown_components_safely():
    rule = MigrationRuleRepository().component_rule("tLegacyThing")
    assert rule["status"] == "UNKNOWN"
    assert rule["auto_fix"] is False

