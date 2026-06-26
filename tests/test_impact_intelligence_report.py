import json
from app.ui.impact_intelligence_dashboard import build_impact_intelligence, export_impact_intelligence, impact_report_markdown


def test_report_sections_and_exports():
    jobs = [{"job_data": {"job_name": "A", "components": [{"component_type": "tMysqlInput"}]},
             "column_mappings": [{"source_table": "raw", "source_column": "id", "target_table": "mart", "target_column": "id"}]}]
    data = build_impact_intelligence(jobs)
    report = impact_report_markdown(data)
    for heading in ("Component Risk Analysis", "Deprecated Components", "Component Usage", "Column Lineage", "Transformation Intelligence", "Critical Assets"):
        assert heading in report
    assert json.loads(export_impact_intelligence(data, "json"))["component_usage"]["total_instances"] == 1
    assert export_impact_intelligence(data, "html").startswith(b"<!doctype html>")
    assert export_impact_intelligence(data, "pdf").startswith(b"%PDF")
    assert export_impact_intelligence(data, "xlsx").startswith(b"PK")
