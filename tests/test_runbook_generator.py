from app.runbook import MigrationRunbookGenerator


def test_runbook_generator_outputs_required_sections():
    jobs = [{"job_data": {"job_name": "j1", "components": [{"component_type": "tMap"}]}}]
    rb = MigrationRunbookGenerator().generate(jobs)
    assert rb["migration_overview"]["jobs"] == 1
    assert rb["migration_phases"]
    assert rb["rollback_plan"]
    assert rb["cutover_plan"]
    assert rb["technical_runbook"]["job_by_job_activities"]
    assert rb["executive_runbook"]["milestones"]
    assert "Migration Runbook" in MigrationRunbookGenerator().export(rb, "html")
