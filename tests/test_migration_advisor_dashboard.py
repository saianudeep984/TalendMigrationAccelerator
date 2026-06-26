from app.parser.project_classifier import ProjectType
from app.ui.migration_advisor_dashboard import build_migration_advisor_dashboard


def test_dashboard_data_open_studio():
    data = build_migration_advisor_dashboard(ProjectType.OPEN_STUDIO, "Talend 7")
    assert data["projectType"] == "Open Studio"
    assert data["sourceVersion"] == "Talend 7"
    assert data["targetVersion"] in ("Talend 8", "Talend Cloud")
    assert "Import into Talend 8" in data["recommendedActions"]


def test_dashboard_data_unsupported_source():
    data = build_migration_advisor_dashboard(ProjectType.OPEN_STUDIO, "Talend 6")
    assert data["targetVersion"] is None
    assert data["recommendedActions"] == []


def test_dashboard_data_enterprise_with_mdm_prefers_cloud():
    data = build_migration_advisor_dashboard(
        ProjectType.ENTERPRISE, "Talend 7.3", enterprise_features={"summary": ["MDM"]}
    )
    assert data["targetVersion"] == "Talend Cloud"
    assert data["recommendedActions"][-1] == "Perform cloud optimization"
