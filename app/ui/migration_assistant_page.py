"""
Migration Assistant Page
Full UX: Before → During → After Open Studio → Talend 8 migration.
"""

import streamlit as st

from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag

def _cloud_rag(cr: dict) -> str:
    """Get RAG status from a cloud_readiness dict (supports RAG status fields)."""
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return _score_to_rag(cr.get("score", 0))

import zipfile
import os
import shutil

from app.utils.zip_extractor import safe_extract
from app.parser.repository_scanner import find_talend_jobs
from app.parser.talend_xml_parser import TalendJobParser
from app.cache.cache_manager import CacheManager as _CacheManager

_tma_cache = _CacheManager()
from app.analyzers.complexity_analyzer import calculate_complexity
from app.analyzers.component_analyzer import analyze_components
from app.analyzers.deprecated_checker import analyze_component_risks
from app.analyzers.cloud_readiness import calculate_cloud_readiness
from app.risk_engine.risk_analyzer import RiskAnalyzer

from app.precheck.repository_validator import RepositoryValidator
from app.precheck.repository_health import RepositoryHealth
from app.precheck.migration_blockers import MigrationBlockers
from app.analyzers.readiness_scorer import Talend8Readiness, MigrationReadiness
from app.migration_assistant.studio_import_guide import StudioImportGuide
from app.post_migration.migration_failure_detector import MigrationFailureDetector
from app.post_migration.repository_compare import RepositoryCompare
from app.post_migration.runtime_validation import RuntimeValidation
from app.cloud_modernization.cloud_optimizer import CloudOptimizer
from app.remediation.remediation_tracker import RemediationTracker


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def _extract_zip(zip_path: str, extract_to: str) -> list:

    if os.path.exists(extract_to):
        shutil.rmtree(extract_to)

    os.makedirs(extract_to, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        file_list = zf.namelist()

    safe_extract(zip_path, extract_to)

    return file_list


def _parse_jobs(job_files: list) -> list:

    all_jobs = []
    risk_engine = RiskAnalyzer()

    for file in job_files:

        try:

            job_data = _tma_cache.load_or_parse(file)

            if job_data["job_name"] == "INVALID_JOB":
                continue

            all_jobs.append({
                "job_data": job_data,
                "complexity": calculate_complexity(job_data),
                "component_summary": analyze_components(job_data),
                "legacy_risk_report": analyze_component_risks(job_data),
                "cloud_readiness": calculate_cloud_readiness(job_data),
                "enterprise_risk_report": risk_engine.analyze(job_data)
            })

        except Exception:
            pass

    return all_jobs


def _severity_color(severity: str) -> str:

    colors = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "WARNING": "🟡",
        "LOW": "🟢"
    }

    return colors.get(severity, "⚪")


# ---------------------------------------------------
# Phase Display Functions
# ---------------------------------------------------

def _show_validation(file_list: list, job_count: int):

    st.subheader("📋 Step 1 — Repository Validation")

    validator = RepositoryValidator()
    health_engine = RepositoryHealth()

    errors = validator.validate(file_list)
    health = health_engine.score(errors, job_count, file_list)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Health Status", health["health_status"])
    col2.metric("Health Status", health["health_status"])
    col3.metric("Jobs Found", health["job_count"])
    col4.metric("Ready for Migration", "✅ YES" if health["ready_for_migration"] else "❌ NO")

    if errors:

        st.error("**Validation Errors:**")

        for err in errors:
            st.markdown(f"- ❌ {err}")

    else:

        st.success("✅ Repository structure is valid")

    if health["warnings"]:

        st.warning("**Warnings:**")

        for w in health["warnings"]:
            st.markdown(f"- ⚠️ {w}")

    return health["ready_for_migration"]


def _show_compatibility(all_jobs: list):

    st.subheader("🔍 Step 2 — Compatibility Scan")

    blocker_engine = MigrationBlockers()
    readiness_engine = Talend8Readiness()

    blockers = blocker_engine.detect(all_jobs)
    repo_readiness = readiness_engine.evaluate_repository(all_jobs)

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Talend 8 Readiness",
        "GREEN" if repo_readiness['overall_score'] >= 70 else ("AMBER" if repo_readiness['overall_score'] >= 40 else "RED"),
        delta=repo_readiness["overall_status"]
    )

    col2.metric(
        "Hard Blockers",
        blockers["hard_blocker_count"],
        delta="CRITICAL" if blockers["hard_blocker_count"] > 0 else "CLEAR",
        delta_color="inverse"
    )

    col3.metric(
        "Soft Blockers",
        blockers["soft_blocker_count"],
        delta="WARNINGS" if blockers["soft_blocker_count"] > 0 else "CLEAR",
        delta_color="off"
    )

    if blockers["hard_blockers"]:

        st.error("**🔴 Hard Blockers — Must Fix Before Migration:**")

        for b in blockers["hard_blockers"]:

            st.markdown(
                f"- {_severity_color(b['severity'])} "
                f"**{b['job']}** → `{b['component']}` — {b['action']}"
            )

    if blockers["soft_blockers"]:

        with st.expander("⚠️ Soft Blockers — Review Recommended"):

            for b in blockers["soft_blockers"]:

                st.markdown(
                    f"- {_severity_color(b['severity'])} "
                    f"**{b['job']}** → `{b['component']}` — {b['action']}"
                )

    # Per-job readiness
    with st.expander("📊 Per-Job Talend 8 Readiness"):

        for result in repo_readiness["job_results"]:

            status = result["status"]
            name = result["job_name"]

            st.markdown(
                f"**{name}** - {status}"
            )

            if result["blockers"]:

                for b in result["blockers"]:
                    st.markdown(
                        f"  - ❌ `{b['component']}` — {b['reason']}"
                    )

    return blockers


def _show_migration_readiness(all_jobs: list):

    st.subheader("📊 Step 3 — Migration Readiness Status")

    readiness_engine = MigrationReadiness()
    readiness = readiness_engine.evaluate(all_jobs)
    status = readiness["status"]
    if status in ("GREEN", "Ready", "LOW"):
        st.success("### Cloud Readiness Status: GREEN")
    elif status in ("AMBER", "Partially Ready", "MEDIUM"):
        st.warning("### Cloud Readiness Status: AMBER")
    else:
        st.error("### Cloud Readiness Status: RED")

    col1, col2 = st.columns(2)

    col1.metric(
        "High Risk Components",
        readiness["high_risk_components"]
    )

    col2.metric(
        "Cloud Blockers",
        readiness["cloud_blockers"]
    )

    return readiness


def _show_ai_remediation(all_jobs: list, blockers: dict):

    st.subheader("🤖 Step 4 — AI Remediation Guidance")

    tracker = RemediationTracker()
    tracker.build_from_blockers(blockers)
    summary = tracker.get_summary()

    col1, col2, col3 = st.columns(3)

    col1.metric("Total Issues", summary["total_tasks"])
    col2.metric("Pending Fix", summary["pending"])
    col3.metric("Completion", f"{summary['completion_pct']}%")

    if blockers["hard_blocker_count"] > 0:

        st.error("**Remediation Actions Required:**")

        for b in blockers["hard_blockers"]:

            with st.expander(
                f"🔴 {b['job']} → {b['component']}"
            ):

                st.markdown(f"**Severity:** {b['severity']}")
                st.markdown(f"**Action:** {b['action']}")

                st.markdown(
                    "**Replacement Guide:**\n"
                    f"- Remove `{b['component']}` from job design\n"
                    "- Identify equivalent Talend 8 component\n"
                    "- Remap input/output connections\n"
                    "- Test in Talend 8 Studio sandbox"
                )

    else:

        st.success(
            "✅ No hard blockers found. "
            "Repository is clean for migration."
        )


def _show_migration_guide():

    st.subheader("🚀 Step 5 — Migration Execution Guide")

    guide = StudioImportGuide()
    steps = guide.generate()

    # Visual flow diagram
    st.markdown("""
    ```
    Open Studio ZIP
         ↓
    Talend 8 Studio Import
         ↓
    Internal Migration Tasks Run
         ↓
    Review Invalid Items
         ↓
    Apply Fixes
         ↓
    Export Migrated Repository
    ```
    """)

    st.markdown("---")

    for step in steps:

        icon = ["📁", "📥", "⚙️", "🔍", "🛠️", "📤"][step["step"] - 1]

        with st.expander(
            f"{icon} Step {step['step']} — {step['title']}",
            expanded=(step["step"] <= 2)
        ):

            st.write(step["details"])

            # Extra detailed guidance per step
            if step["step"] == 1:

                st.info(
                    "**Talend 8 Studio** = Talend Data Integration 8.x\n\n"
                    "Download from Talend Portal: "
                    "https://www.talend.com/download/"
                )

            elif step["step"] == 2:

                st.warning(
                    "⚠️ Use your **ORIGINAL Open Studio Export ZIP** — "
                    "NOT a modified version.\n\n"
                    "In Talend 8 Studio:\n"
                    "1. File → Import → Talend Items\n"
                    "2. Select 'ZIP Archive'\n"
                    "3. Browse to your exported ZIP\n"
                    "4. Select Project and click Finish"
                )

            elif step["step"] == 3:

                st.info(
                    "Talend 8 will automatically:\n"
                    "- Run EMF model migration\n"
                    "- Regenerate internal signatures\n"
                    "- Update component versions\n"
                    "- Flag incompatible items\n\n"
                    "This may take 1-10 minutes depending on repo size."
                )

            elif step["step"] == 4:

                st.warning(
                    "After import, check:\n"
                    "- **Problems View** (Window → Show View → Problems)\n"
                    "- Items marked with red/yellow icons\n"
                    "- Context variables that couldn't be migrated\n"
                    "- Removed or unsupported components"
                )

            elif step["step"] == 5:

                st.info(
                    "Use the AI Remediation guidance from Step 4 above "
                    "to fix each flagged item in Talend 8 Studio."
                )

            elif step["step"] == 6:

                st.info(
                    "After fixing:\n"
                    "1. Right-click Project in Repository View\n"
                    "2. Export → Talend Items → ZIP Archive\n"
                    "3. Upload that ZIP into this platform's "
                    "**Post-Migration Validation** section"
                )


def _show_post_migration(all_jobs: list):

    st.subheader("✅ Post-Migration Validation")

    st.info(
        "Upload your **Talend 8 exported ZIP** below "
        "to validate the migrated repository."
    )

    uploaded_post = st.file_uploader(
        "Upload Talend 8 Migrated Repository ZIP",
        type=["zip"],
        key="post_migration_upload"
    )

    if not uploaded_post:
        return

    post_zip_path = "post_migration_repo.zip"
    post_extract = "post_migration_temp"

    with open(post_zip_path, "wb") as f:
        f.write(uploaded_post.getbuffer())

    with st.spinner("Extracting migrated repository..."):
        _extract_zip(post_zip_path, post_extract)

    post_jobs_files = find_talend_jobs(post_extract)

    with st.spinner("Parsing migrated jobs..."):
        post_jobs = _parse_jobs(post_jobs_files)

    st.success(
        f"Found {len(post_jobs)} jobs in migrated repository"
    )

    # Failure Detection
    st.markdown("#### 🔍 Migration Failure Detection")

    failure_detector = MigrationFailureDetector()
    failures = failure_detector.detect(post_jobs)

    if failures:

        st.error(f"Found {len(failures)} migration failures:")

        for f in failures:
            st.markdown(
                f"- ❌ **{f['job']}** — {f['issue']}"
            )

    else:

        st.success("✅ No migration failures detected")

    # Runtime Validation
    st.markdown("#### ⚙️ Runtime Validation")

    runtime = RuntimeValidation()
    runtime_result = runtime.validate(post_jobs)

    col1, col2 = st.columns(2)

    col1.metric(
        "Jobs Passed",
        len(runtime_result["jobs_passed"])
    )

    col2.metric(
        "Jobs with Issues",
        len(runtime_result["jobs_with_issues"])
    )

    if runtime_result["jobs_with_issues"]:

        for item in runtime_result["jobs_with_issues"]:

            with st.expander(f"⚠️ {item['job']}"):

                for issue in item["issues"]:

                    st.markdown(
                        f"- {_severity_color(issue['severity'])} "
                        f"`{issue['component']}` — {issue['issue']}"
                    )

    # Repo Compare (if pre-migration jobs in session)
    if "pre_migration_jobs" in st.session_state:

        st.markdown("#### 📊 Pre vs Post Comparison")

        comparer = RepositoryCompare()

        compare_result = comparer.compare(
            st.session_state["pre_migration_jobs"],
            post_jobs
        )

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Pre-Migration Jobs",
            compare_result["pre_job_count"]
        )

        col2.metric(
            "Post-Migration Jobs",
            compare_result["post_job_count"]
        )

        col3.metric(
            "Migration Complete",
            "✅ YES" if compare_result["migration_complete"] else "⚠️ PARTIAL"
        )

        if compare_result["jobs_removed"]:

            st.warning(
                "Jobs missing after migration: "
                + ", ".join(compare_result["jobs_removed"])
            )

    # Cloud Optimization
    st.markdown("#### ☁️ Cloud Optimization Recommendations")

    optimizer = CloudOptimizer()
    cloud_result = optimizer.optimize(post_jobs)

    col1, col2 = st.columns(2)

    col1.metric(
        "Cloud Ready Jobs",
        len(cloud_result["cloud_ready_jobs"])
    )

    col2.metric(
        "Cloud Readiness",
        "GREEN" if cloud_result['cloud_readiness_pct'] >= 70 else ("AMBER" if cloud_result['cloud_readiness_pct'] >= 40 else "RED")
    )

    if cloud_result["job_recommendations"]:

        with st.expander(
            "☁️ Cloud Modernization Recommendations"
        ):

            for rec in cloud_result["job_recommendations"]:

                st.markdown(f"**{rec['job']}** ({rec['count']} recommendations)")

                for r in rec["recommendations"]:

                    st.markdown(
                        f"  - Replace `{r['component']}` "
                        f"→ **{r['cloud_replacement']}** "
                        f"({r['benefit']})"
                    )


# ---------------------------------------------------
# MAIN PAGE RENDERER
# ---------------------------------------------------

def render_migration_assistant():

    st.header("🚀 Migration Assistant")

    st.markdown(
        "**AI-Powered Open Studio → Talend 8 Migration Platform**\n\n"
        "Follow the steps below: Upload your Open Studio ZIP, "
        "get analysis + guidance, then import into Talend 8 Studio."
    )

    # --- Phase Tabs ---
    tab_before, tab_during, tab_after = st.tabs([
        "📦 BEFORE MIGRATION",
        "⚙️ DURING MIGRATION",
        "✅ AFTER MIGRATION"
    ])

    # ===================================================
    # TAB 1 — BEFORE MIGRATION
    # ===================================================

    with tab_before:

        st.markdown("### Upload Your Open Studio Repository ZIP")

        uploaded_file = st.file_uploader(
            "Upload Open Studio Export ZIP",
            type=["zip"],
            key="pre_migration_upload",
            help="Export from Talend Open Studio: File → Export → Talend Items → ZIP"
        )

        if not uploaded_file:

            st.info(
                "**How to export from Open Studio:**\n\n"
                "1. Open Talend Open Studio\n"
                "2. File → Export → Talend Items\n"
                "3. Select **ZIP Archive** format\n"
                "4. Check all items (Jobs, Contexts, Routines, Metadata)\n"
                "5. Click **Finish** → Upload the ZIP here"
            )

            return

        # Save and extract
        zip_path = "pre_migration_repo.zip"
        extract_to = "pre_migration_temp"

        with open(zip_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.spinner("Extracting repository..."):
            file_list = _extract_zip(zip_path, extract_to)

        with st.spinner("Scanning jobs..."):
            job_files = find_talend_jobs(extract_to)

        with st.spinner("Parsing jobs..."):
            all_jobs = _parse_jobs(job_files)

        # Store in session
        st.session_state["pre_migration_jobs"] = all_jobs
        st.session_state["pre_migration_file_list"] = file_list

        st.success(
            f"✅ Repository loaded — "
            f"{len(all_jobs)} jobs found"
        )

        st.markdown("---")

        # --- Step 1: Validation ---
        valid = _show_validation(file_list, len(all_jobs))

        if not valid:
            st.error(
                "❌ Fix validation errors before proceeding."
            )
            return

        st.markdown("---")

        # --- Step 2: Compatibility ---
        blockers = _show_compatibility(all_jobs)

        st.markdown("---")

        # --- Step 3: Readiness ---
        _show_migration_readiness(all_jobs)

        st.markdown("---")

        # --- Step 4: AI Remediation ---
        _show_ai_remediation(all_jobs, blockers)

        st.markdown("---")

        # --- Step 5: Guide ---
        st.info(
            "✅ Analysis complete. "
            "Switch to **DURING MIGRATION** tab for import steps."
        )

    # ===================================================
    # TAB 2 — DURING MIGRATION
    # ===================================================

    with tab_during:

        st.markdown(
            "### Import Your ZIP into Talend 8 Studio\n\n"
            "This step happens **inside Talend 8 Studio** — "
            "not in this platform. Follow the guide below."
        )

        _show_migration_guide()

        st.markdown("---")

        st.warning(
            "⚠️ **Important:** Do NOT upload a modified ZIP. "
            "Always use the **original Open Studio Export ZIP**. "
            "Talend 8 Studio handles the internal migration automatically."
        )

        st.success(
            "Once migration is complete in Talend 8 Studio, "
            "export the repository and come back to the "
            "**AFTER MIGRATION** tab."
        )

    # ===================================================
    # TAB 3 — AFTER MIGRATION
    # ===================================================

    with tab_after:

        st.markdown(
            "### Validate Your Migrated Talend 8 Repository\n\n"
            "Export from Talend 8 Studio and upload below."
        )

        _show_post_migration(all_jobs if "pre_migration_jobs" not in st.session_state else st.session_state["pre_migration_jobs"])

        st.markdown("---")
        # Cloud push panel — Fix 3
        try:
            from app.cloud_integration.cloud_push_ui import render_cloud_push_panel
            render_cloud_push_panel(
                all_jobs=st.session_state.get("last_analysis_jobs")
            )
        except Exception as _cp_err:
            st.warning(f"Cloud push panel unavailable: {_cp_err}")
