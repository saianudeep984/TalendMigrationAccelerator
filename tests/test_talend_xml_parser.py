from app.parser.talend_xml_parser import TalendJobParser


def test_talend_xml_parser_parses_sample_item():
    parser = TalendJobParser("sample_projects/Sample.item")
    job = parser.extract_job_info()

    assert job["job_name"] == "Sample"
    assert job["job_version"] == "0.1"
    assert len(job["components"]) >= 1
    assert any(component["component_type"] == "tLogRow" for component in job["components"])
