from app.analyzers.models import UpgradePathResult, UpgradeWarning, CompatibilityStatus
from app.analyzers.version_upgrade_analyzer import UpgradePathAnalyzer
from app.tiap.migration_assessment.migration_assessment import get_upgrade_path, build_migration_assessment
from app.api.migration_api import get_upgrade_path_result, get_upgrade_path_results
from app.api.routes import call_route


def _job(source_version, components):
    return {
        "job_name": "TestJob",
        "source_version": source_version,
        "components": [{"component_type": c} for c in components],
    }


def test_build_hops():
    a = UpgradePathAnalyzer()
    assert a.build_hops("Talend 6", "Talend 8") == ["6_to_7", "7_to_8"]
    assert a.build_hops("Talend 8", "Talend 6") == []
    assert a.build_hops("Talend 7", "Talend 7") == []


def test_analyze_job_findings():
    job = _job("Talend 6", ["tFTPGet", "tJavaFlex", "tMom", "tMap"])
    result = UpgradePathAnalyzer().analyze_job(job, "Talend 6", "Talend 8")
    impacts = {f["component"]: f["impact"] for f in result["componentFindings"]}
    assert impacts["tFTPGet"] == "RENAMED"
    assert impacts["tJavaFlex"] == "REMOVED"
    assert impacts["tMom"] == "UNSUPPORTED"
    assert "tMap" not in impacts


def test_analyze_job_warnings_and_blockers():
    job = _job("Talend 6", ["tJavaFlex", "tMom"])
    result = UpgradePathAnalyzer().analyze_job(job, "Talend 6", "Talend 8")
    categories = {w["category"] for w in result["warnings"]}
    assert "DEPRECATED" in categories
    assert "UNSUPPORTED" in categories
    assert result["blockers"] == []


def test_unsupported_path_blocker():
    job = _job("Talend 8", ["tMap"])
    result = UpgradePathAnalyzer().analyze_job(job, "Talend 8", "Talend 6")
    assert result["supported"] is False
    assert len(result["blockers"]) == 1


def test_upgrade_path_result_round_trip():
    job = _job("Talend 6", ["tFTPGet", "tJavaFlex", "tMom"])
    raw = UpgradePathAnalyzer().analyze_job(job, "Talend 6", "Talend 8")
    result = UpgradePathResult.from_dict(raw)
    rebuilt = result.to_dict()
    for key, value in raw.items():
        assert rebuilt[key] == value


def test_upgrade_path_result_full_pipeline_round_trip():
    job = _job("Talend 6", ["tFTPGet", "tJavaFlex", "tMom"])
    enriched = get_upgrade_path(job, target_version="Talend 8")
    result = UpgradePathResult.from_dict(enriched)
    assert result.to_dict() == enriched


def test_upgrade_warning_round_trip():
    w = UpgradeWarning(component="tMom", category="UNSUPPORTED", message="msg", severity="HIGH")
    d = w.to_dict()
    assert UpgradeWarning.from_dict(d).to_dict() == d


def test_compatibility_status_compatible():
    job = _job("Talend 7", ["tMap"])
    result = get_upgrade_path(job, target_version="Talend 8")
    assert result["compatibilityStatus"] == CompatibilityStatus.COMPATIBLE.value
    assert result["blockers"] == []


def test_compatibility_status_conditional():
    job = _job("Talend 6", ["tFTPGet", "tJavaFlex"])
    result = get_upgrade_path(job, target_version="Talend 8")
    assert result["compatibilityStatus"] == CompatibilityStatus.CONDITIONAL.value


def test_compatibility_status_not_compatible():
    job = _job("Talend 8", ["tMap"])
    result = get_upgrade_path(job, target_version="Talend 6")
    assert result["compatibilityStatus"] == CompatibilityStatus.NOT_COMPATIBLE.value
    assert len(result["blockers"]) >= 1


def test_get_upgrade_path_reads_source_version_from_job_data():
    job = _job("Talend 6", ["tMap"])
    result = get_upgrade_path(job, target_version="Talend 8")
    assert result["sourceVersion"] == "Talend 6"


def test_get_upgrade_path_defaults_source_version():
    job = {"job_name": "NoVersion", "components": [{"component_type": "tMap"}]}
    result = get_upgrade_path(job, target_version="Talend 8")
    assert result["sourceVersion"] == "Talend 7"


def test_migration_path_populated():
    job = _job("Talend 6", ["tMap"])
    result = get_upgrade_path(job, target_version="Talend 8")
    assert result["migrationPath"][0] == "Talend 6"
    assert result["migrationPath"][-1] == "Talend 8"


def test_build_migration_assessment_includes_upgrade_path():
    job = _job("Talend 6", ["tFTPGet", "tJavaFlex"])
    out = build_migration_assessment(job, target_version="Talend 8")
    assert "upgrade_path" in out
    assert out["upgrade_path"]["compatibilityStatus"] == CompatibilityStatus.CONDITIONAL.value
    assert any("Upgrade impact" in r for r in out["recommendations"])


def test_api_get_upgrade_path_result():
    job = _job("Talend 6", ["tMom"])
    result = get_upgrade_path_result(job, target_version="Talend 8")
    assert result["compatibilityStatus"] in (
        CompatibilityStatus.COMPATIBLE.value,
        CompatibilityStatus.CONDITIONAL.value,
        CompatibilityStatus.NOT_COMPATIBLE.value,
    )


def test_api_get_upgrade_path_results_list():
    jobs = [{"job_data": _job("Talend 6", ["tMom"])}, {"job_data": _job("Talend 7", ["tMap"])}]
    results = get_upgrade_path_results(jobs, target_version="Talend 8")
    assert len(results) == 2


def test_route_registration():
    job = _job("Talend 6", ["tMom"])
    result = call_route("upgrade_path_result", job, target_version="Talend 8")
    assert "compatibilityStatus" in result
    results = call_route("upgrade_path_results", [{"job_data": job}], target_version="Talend 8")
    assert isinstance(results, list) and len(results) == 1
