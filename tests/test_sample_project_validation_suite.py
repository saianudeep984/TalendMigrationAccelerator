from app.validation.sample_project_validation_suite import run_validation_suite


def test_full_suite_100_percent_accuracy():
    report = run_validation_suite()
    assert report["detection_accuracy"] == 1.0
    assert report["recommendation_accuracy"] == 1.0


def test_open_studio_fixture_detected_correctly():
    report = run_validation_suite()
    row = next(r for r in report["results"] if r["name"] == "open_studio_7_3")
    assert row["detected_project_type"] == "Open Studio"
    assert row["recommended_target"] == "Talend 8"


def test_enterprise_fixture_detected_correctly():
    report = run_validation_suite()
    row = next(r for r in report["results"] if r["name"] == "enterprise_7_3")
    assert row["detected_project_type"] == "Enterprise"
    assert row["recommended_target"] == "Talend 8"


def test_enterprise_mdm_fixture_recommends_cloud():
    report = run_validation_suite()
    row = next(r for r in report["results"] if r["name"] == "enterprise_7_4_with_mdm")
    assert row["recommended_target"] == "Talend Cloud"


def test_failing_fixture_lowers_accuracy():
    bad_fixture = {
        "name": "bad",
        "product_version": "Talend Open Studio for Data Integration-7.3.1",
        "storage_type": "local",
        "expected_project_type": "WRONG_TYPE",
        "expected_source_version": "Talend 7",
        "component_usage": [],
        "enterprise_features": {},
        "expected_target_version": "Talend 8",
    }
    report = run_validation_suite([bad_fixture])
    assert report["detection_accuracy"] == 0.0
