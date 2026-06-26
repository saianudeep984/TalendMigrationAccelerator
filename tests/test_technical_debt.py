from app.architecture.anti_pattern_detector import ArchitectureAntiPatternDetector
from app.architecture.technical_debt_engine import TechnicalDebtEngine


def test_technical_debt_prioritizes_highest_risk_assets():
    jobs = [{"job_data": {"job_name": "Risky", "components": [
        {"component_type": "tJava"}, {"component_type": "tJavaRow"}, {"component_type": "tJavaFlex"},
        {"component_type": "tMysqlInput", "parameters": {"password": "secret"}},
    ]}}]
    anti = ArchitectureAntiPatternDetector().detect(jobs)
    debt = TechnicalDebtEngine().calculate(anti)
    assert debt["technical_debt_score"] > 0
    assert debt["highest_risk_assets"][0]["asset"] == "Risky"
    assert debt["remediation_items"][0]["priority"] in {"P1", "P2"}

