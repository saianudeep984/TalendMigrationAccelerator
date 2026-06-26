from app.portfolio import EnterprisePortfolioPlatform, analyze_portfolio
from app.ui.portfolio_dashboard import export_portfolio, portfolio_report_markdown


def _job(name, components):
    return {"job_name": name, "components": [{"type": c, "componentName": c, "properties": {}} for c in components]}


def test_portfolio_multi_project_analysis():
    projects = [
        {"project_name": "Finance", "jobs": [_job("load_gl", ["tFileInputDelimited", "tMap", "tMysqlOutput"])]},
        {"project_name": "Risk", "jobs": [_job("risk_feed", ["tJava", "tMap", "tOracleOutput"])]},
    ]
    result = analyze_portfolio(projects, {"hourly_rate": 100})
    assert result["summary"]["project_count"] == 2
    assert result["kpi_tracking"]["projects_analyzed"] == 2
    assert "portfolio_readiness_score" in result["readiness_dashboard"]
    assert result["migration_effort"]["cost"]["hourly_rate"] == 100
    assert result["wave_planning"]["portfolio_wave_count"] >= 1
    assert "cio_dashboard" in result
    assert "architect_dashboard" in result
    assert "program_management_dashboard" in result


def test_portfolio_risk_debt_roadmap_exports():
    projects = [
        {"name": "LegacyA", "jobs": [_job("a", ["tJava", "tJavaRow", "tMap"])]},
        {"name": "LegacyB", "jobs": [_job("b", ["tFileInputDelimited", "tMap"])]},
    ]
    result = EnterprisePortfolioPlatform().analyze(projects)
    assert result["cross_project_risks"]["highest_risk_projects"]
    assert "portfolio_debt_score" in result["technical_debt_analysis"]
    assert "timeline" in result["organization_roadmap"]
    assert "Enterprise Portfolio Migration Report" in portfolio_report_markdown(result)
    assert "LegacyA" in export_portfolio(result, "json")
