from app.parser.project_classifier import ProjectType
from app.migration_guidance.workflow_selector import WorkflowSelector, select_workflow


def test_open_studio_direct_path():
    result = select_workflow(ProjectType.OPEN_STUDIO, "Talend 7", "Talend 8")
    assert result["projectType"] == "Open Studio"
    assert "Import into Talend 8" in result["steps"]
    assert "Perform intermediate version upgrade before final target" not in result["steps"]


def test_enterprise_workflow_has_tac_steps():
    result = select_workflow(ProjectType.ENTERPRISE, "Talend 7", "Talend 8")
    assert any("TAC" in s for s in result["steps"])
    assert any("Job Servers" in s for s in result["steps"])


def test_cloud_target_appends_optimization_step():
    result = select_workflow(ProjectType.OPEN_STUDIO, "Talend 7", "Talend Cloud")
    assert result["steps"][-1] == "Perform cloud optimization"


def test_multi_hop_inserts_intermediate_step():
    result = select_workflow(ProjectType.OPEN_STUDIO, "Talend 6", "Talend 8")
    assert len(result["hops"]) > 1
    assert "Perform intermediate version upgrade before final target" in result["steps"]


def test_string_project_type_accepted():
    result = WorkflowSelector().select_workflow("Cloud", "Talend 7", "Talend Cloud")
    assert result["projectType"] == "Cloud"
