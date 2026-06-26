import json
from app.ui.migration_intelligence_dashboard import build_migration_intelligence, executive_report_markdown, export_migration_intelligence


def test_executive_report_and_all_exports():
    data = build_migration_intelligence([{"job_data": {"job_name": "A", "components": [{"component_type": "tMap"}]}}], {"score": 90})
    report = executive_report_markdown(data)
    for section in ("Migration Complexity Summary", "Effort Estimation", "Migration Strategy", "Wave Plan", "Critical Dependencies", "Risk Breakdown"):
        assert section in report
    assert json.loads(export_migration_intelligence(data, "json"))["complexity"]["job_count"] == 1
    assert export_migration_intelligence(data, "html").startswith(b"<!doctype html>")
    assert export_migration_intelligence(data, "pdf").startswith(b"%PDF")
    assert export_migration_intelligence(data, "xlsx").startswith(b"PK")
