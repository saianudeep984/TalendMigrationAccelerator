import streamlit as st

from app.tiap.inventory.inventory_parser import InventoryParser
from app.tiap.profiling.component_profiler import ComponentProfiler
from app.analyzers.readiness_scorer import RepositoryScoring
from app.analyzers.models import RepositoryOverview
from app.tiap.documentation.repository_doc_generator import RepositoryDocGenerator
from app.tiap.refactoring.technical_debt_detector import TechnicalDebtDetector
from app.tiap.testing.regression_suite_builder import RegressionSuiteBuilder
from app.tiap.governance.compliance_assessor import ComplianceAssessor
from app.repository.repository_type_detector import RepositoryTypeDetector
from app.repository.enterprise_feature_detector import EnterpriseFeatureDetector
from app.analyzers.version_upgrade_analyzer import UpgradePathAnalyzer
from app.analyzers.version_compatibility_engine import VersionCompatibilityEngine
from app.risk_engine.risk_analyzer import RiskAnalyzer
from app.ui.design_system_v2 import render_kpi_row, panel_open, panel_close, section_header, RepositoryOverviewCard


def render_repository_summary(job_data, repository_path: str = None, repository: dict = None):
    if isinstance(job_data, list):
        _render_repository(job_data, repository_path=repository_path, repository=repository)
        return

    st.subheader(f"Job Summary - {job_data.get('job_name', 'Unknown')}")
    comps = [c.get("component_type") for c in job_data.get("components", [])]
    st.metric("Components", len(comps))
    st.write("Technical Flow")
    for component in comps[:50]:
        st.write(f"-> {component}")


def _render_repository(all_jobs, repository_path: str = None, repository: dict = None):
    # PHASE 2 UI REFACTOR
    inventory = InventoryParser().build_inventory(all_jobs)
    component_profile = ComponentProfiler().profile(all_jobs)
    scoring = RepositoryScoring().score(all_jobs)
    debt = TechnicalDebtDetector().analyze(all_jobs)
    testing = RegressionSuiteBuilder().build(all_jobs)
    governance = ComplianceAssessor().assess(all_jobs)
    docs = RepositoryDocGenerator().generate(all_jobs)
    kpis = inventory.get("kpis", {})
    dist = component_profile.get("component_distribution", {})

    if repository is not None:
        repo_type_info = RepositoryTypeDetector().detect_from_repository(repository)
    elif repository_path:
        repo_type_info = {
            "type": RepositoryTypeDetector().detect_from_path(repository_path).get("type", "Unknown"),
            "source_version": RepositoryTypeDetector().extract_source_version_from_path(repository_path),
        }
    else:
        repo_type_info = {"type": "Unknown", "source_version": "UNKNOWN"}

    enterprise_features_info = EnterpriseFeatureDetector().detect_from_jobs(all_jobs)

    source_version = repo_type_info.get("source_version", "UNKNOWN")
    target_version = "Talend 8"
    target_versions = [t["version"] for t in VersionCompatibilityEngine().get_supported_targets(source_version)] \
        if source_version not in (None, "UNKNOWN") else []

    _risk_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    repo_risk = "LOW"
    total_findings = 0
    total_blockers = 0
    for job_entry in all_jobs:
        job = job_entry.get("job_data", job_entry) if isinstance(job_entry, dict) else job_entry
        for r in RiskAnalyzer().analyze(job):
            if _risk_rank.get(r.get("risk", "LOW"), 0) > _risk_rank.get(repo_risk, 0):
                repo_risk = r.get("risk", "LOW")
        if source_version not in (None, "UNKNOWN"):
            path_result = UpgradePathAnalyzer().analyze_job(job, source_version, target_version)
            total_findings += len(path_result.get("componentFindings", []))
            total_blockers += len(path_result.get("blockers", []))

    if source_version in (None, "UNKNOWN"):
        upgrade_path_summary = "Source version unknown — upgrade path could not be determined."
    elif total_blockers:
        upgrade_path_summary = f"{total_blockers} job(s) blocked from {source_version} to {target_version}."
    elif total_findings:
        upgrade_path_summary = f"{total_findings} component change(s) required to upgrade from {source_version} to {target_version}."
    else:
        upgrade_path_summary = f"Clean upgrade path available from {source_version} to {target_version}."

    upgrade_path_info = {
        "targetVersions": target_versions,
        "migrationRisk": repo_risk,
        "summary": upgrade_path_summary,
    }

    overview = RepositoryOverview.from_inventory_and_scoring(
        inventory, scoring, repo_type_info, enterprise_features_info, upgrade_path_info
    )
    RepositoryOverviewCard(overview)

    panel_open("Validation Summary", "Documentation, technical debt, testing, and governance signals", height=220)
    render_kpi_row([
        {"label": "Generated Docs", "value": str(len(docs)), "color": "#1d4ed8"},
        {"label": "Technical Debt", "value": f"{debt['debt_score']}%", "color": "#b45309"},
        {"label": "Testing Suite", "value": str(testing["testing_readiness_score"]), "color": "#6d28d9"},
        {"label": "PII Risk", "value": f"{governance['pii_detection']['pii_risk_score']}%", "color": "#be123c"},
    ])
    panel_close()
