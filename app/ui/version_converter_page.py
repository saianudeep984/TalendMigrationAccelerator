"""
Version Converter Page — Talend Studio Automation + Manual Guidance.

This page has two modes:
1. If Talend Studio path is provided → attempts CLI-based migration automation
2. Always → provides manual step-by-step import guidance with pre-flight analysis
"""

import streamlit as st
import tempfile
import os
import zipfile
import shutil

from app.studio_automation.full_migration_orchestrator import (
    FullMigrationOrchestrator
)
from app.parser.repository_scanner import find_talend_jobs
from app.parser.talend_xml_parser import TalendJobParser
from app.parser.version_detector import detect_talend_version
from app.precheck.repository_health import RepositoryHealth
from app.precheck.migration_blockers import MigrationBlockers
from app.analyzers.complexity_analyzer import calculate_complexity
from app.analyzers.cloud_readiness import calculate_cloud_readiness
from app.risk_engine.risk_analyzer import RiskAnalyzer
from app.emf.context_item_state_fixer import fix_zip as fix_context_item_state_zip
from app.repository_builder.talend8_repository_builder import Talend8RepositoryBuilder
from app.ui.design_system_v2 import render_kpi_row, panel_open, panel_close, section_header, status_card, render_insights_row
from app.utils.zip_extractor import safe_extract


def _parse_jobs(job_files):
    all_jobs = []
    risk_engine = RiskAnalyzer()
    for file in job_files:
        try:
            parser = TalendJobParser(file)
            job_data = parser.extract_job_info()
            if job_data["job_name"] == "INVALID_JOB":
                continue
            all_jobs.append({
                "job_data": job_data,
                "complexity": calculate_complexity(job_data),
                "cloud_readiness": calculate_cloud_readiness(job_data),
                "enterprise_risk_report": risk_engine.analyze(job_data)
            })
        except Exception:
            pass
    return all_jobs


def render_converter():

    # PHASE 5 UI REFACTOR
    section_header("Conversion Target", "Select versions, upload the repository, and review conversion readiness.")
    selector_col1, selector_col2 = st.columns(2)
    with selector_col1:
        selected_source_version = st.selectbox(
            "Source version",
            ["Auto-detect", "Talend Open Studio", "Talend 7.3", "Talend 7.4", "Talend 8"],
            key="converter_source_version_selector",
        )
    with selector_col2:
        selected_target_version = st.selectbox(
            "Target version",
            ["Talend 8", "Talend Cloud", "Talend 7.4", "Talend 7.3"],
            key="converter_target_version_selector",
        )

    # ---------------------------------------------------
    # Upload ZIP first — always required
    # ---------------------------------------------------

    section_header("Repository Upload")

    uploaded_file = st.file_uploader(
        "Upload Talend Open Studio Repository ZIP",
        type=["zip"],
        key="converter_upload"
    )

    if not uploaded_file:
        with st.expander("Export guidance", expanded=False):
            st.info(
                "**How to export from Open Studio:**\n\n"
                "1. Open Talend Open Studio\n"
                "2. **File → Export → Talend Items**\n"
                "3. Select **ZIP Archive** format\n"
                "4. Check all items (Jobs, Contexts, Routines, Metadata)\n"
                "5. Click **Finish** → upload the ZIP here"
            )
        return

    # Save and extract
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "source_repository.zip")
    extract_path = os.path.join(temp_dir, "extracted")

    with open(zip_path, "wb") as f:
        f.write(uploaded_file.read())

    with st.spinner("Extracting repository..."):
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            file_list = zf.namelist()
        safe_extract(zip_path, extract_path)

    # ---------------------------------------------------
    # Pre-flight Analysis
    # ---------------------------------------------------

    section_header("Conversion Readiness")

    with st.spinner("Analyzing repository..."):
        job_files = find_talend_jobs(extract_path)
        source_version = detect_talend_version(extract_path)
        all_jobs = _parse_jobs(job_files)

    health_engine = RepositoryHealth()
    blocker_engine = MigrationBlockers()

    health = health_engine.score([], len(all_jobs), file_list)
    blockers = blocker_engine.detect(all_jobs)

    conversion_ready = blockers["hard_blocker_count"] == 0 and health.get("ready_for_migration", False)
    compatibility_score = max(0, 100 - blockers["hard_blocker_count"] * 25 - blockers["soft_blocker_count"] * 5)
    render_kpi_row([
        {"label": "Source Version", "value": source_version or selected_source_version.replace("Auto-detect", "Open Studio"), "caption": "Detected repository", "color": "#1d4ed8"},
        {"label": "Target Version", "value": selected_target_version, "caption": "Selected target", "color": "#0f766e"},
        {"label": "Conversion Readiness", "value": "Ready" if conversion_ready else "Blocked", "caption": health["health_status"], "color": "#15803d" if conversion_ready else "#be123c"},
        {"label": "Compatibility", "value": f"{compatibility_score}%", "caption": f"{blockers['hard_blocker_count']} hard, {blockers['soft_blocker_count']} warnings", "color": "#15803d" if compatibility_score >= 80 else "#b45309"},
    ])

    render_insights_row([
        {"icon": "✅" if conversion_ready else "🚫", "label": "Conversion Status", "value": "Repository is ready for import" if conversion_ready else f"{blockers['hard_blocker_count']} hard blocker(s) must be resolved first", "sub": "Hard blockers prevent successful Studio migration" if not conversion_ready else "Run Studio-assisted import to complete migration", "color": "#15803d" if conversion_ready else "#be123c"},
        {"icon": "🔍", "label": "Compatibility Score", "value": f"{compatibility_score}% compatible with {selected_target_version}", "sub": f"{blockers['soft_blocker_count']} soft warnings to review after import", "color": "#15803d" if compatibility_score >= 80 else "#b45309"},
        {"icon": "📦", "label": "Repository Health", "value": health.get("health_status", "Unknown"), "sub": f"Detected {len(all_jobs)} jobs — use original ZIP for Studio import", "color": "#1d4ed8"},
    ])

    issues_col, recs_col = st.columns(2)
    with issues_col:
        # PHASE 5 UI REFACTOR — fixed-height issues panel.
        panel_open("Issues Panel", "Hard and soft blockers detected during pre-flight", height=280)
        if blockers["hard_blocker_count"] > 0:
            status_card(
                f"{blockers['hard_blocker_count']} hard blocker(s) detected",
                "These components are not supported in the target version and must be replaced before migration.",
                "error",
            )
            for b in blockers["hard_blockers"]:
                st.markdown(f"- **{b['job']}** -> `{b['component']}` - {b['action']}")
        elif blockers["soft_blocker_count"] == 0:
            status_card("No hard blockers", "Repository is ready for target import.", "success")
        else:
            status_card("Warnings only", "Review soft blockers before import.", "warning")
        panel_close()

    with recs_col:
        # PHASE 5 UI REFACTOR — fixed-height recommendations panel.
        panel_open("Recommendations Panel", "Next actions before Studio import", height=280)
        if blockers["hard_blocker_count"] == 0:
            status_card("Import recommended", "Use the original ZIP in Talend Studio so internal migration tasks rebuild metadata.", "success")
        else:
            status_card("Remediation required", "Resolve hard blockers, export again, and rerun pre-flight analysis.", "warning")
        st.markdown("- Keep the original Open Studio ZIP for Studio-assisted import.")
        st.markdown("- Review context and unsupported component warnings before conversion.")
        st.markdown("- Generate the target repository package only after blockers are understood.")
        panel_close()

    if blockers["soft_blocker_count"] > 0:
        with st.expander(f"{blockers['soft_blocker_count']} compatibility warnings to review", expanded=False):
            for b in blockers["soft_blockers"]:
                st.markdown(f"- **{b['job']}** -> `{b['component']}` - {b['action']}")

    if blockers["hard_blocker_count"] == 0:
        st.success("✅ No hard blockers — repository is ready for Talend 8 import")

    # ---------------------------------------------------
    # Migration Guide — always shown
    # ---------------------------------------------------

    section_header("Migration Guidance")

    st.warning(
        "⚠️ **Important:** Talend's migration engine runs **inside Studio** — "
        "it rebuilds EMF metadata, context links, and repository signatures that "
        "cannot be replicated by external tools. Always use the **original ZIP** for import."
    )

    with st.expander("Full Import Guide", expanded=False):
        st.markdown("""
**In Talend 8 Studio:**

1. **Launch** Talend 8 Studio with a clean workspace
2. **Create or open a target Talend 8 project**
3. Inside the project, use **File → Import → Talend Items**
4. Select **ZIP Archive** and browse to your original Open Studio ZIP
5. Click **Next** — Talend will show you the item list
6. Select **all items** (Jobs, Contexts, Routines, Metadata, Connections)
7. Click **Finish**
8. Talend Studio will run its **internal migration tasks** automatically — wait for completion
9. Review any items marked as **invalid** in the Repository panel
10. Fix context variable issues (see remediation guide in Migration Assistant tab)
11. **File → Export → Talend Items → ZIP Archive** to export the migrated repository

Do **not** use the startup-screen **Import an existing project** option for a
job export ZIP. That flow expects a complete Studio project and may fail with
an unhelpful `null` error.

**Context Migration Note:**
The `Contexts ctxCommon 0.1 was invalid` error occurs because Talend Studio rebuilds
`ContextLinkService` and `EMF object graphs` internally during import. This is expected
and handled automatically by Studio — external XML rewriting cannot replicate this.
        """)

    # ---------------------------------------------------
    # Optional: Talend Studio Automation
    # ---------------------------------------------------

    section_header("Optional Studio Automation")

    with st.expander("Automate with Talend Studio CLI", expanded=False):

        st.info(
            "If you have Talend Studio installed, this will:\n"
            "1. Bootstrap a migration workspace\n"
            "2. Extract your repository into the workspace\n"
            "3. Run `migrationcheck` and `migrationreport` CLI commands\n"
            "4. Launch Talend Studio pointed at the prepared workspace\n\n"
            "Requires Talend Studio with `org.talend.commandline.CommandLine` support."
        )

        talend_path = st.text_input(
            "Talend Studio Executable Path",
            value=r"C:\Talend\Talend-Studio-win-x86_64.exe",
            key="talend_path_input"
        )

        if st.button("Attempt CLI Migration", key="cli_migrate_btn"):

            if not os.path.exists(talend_path):
                st.error(
                    f"❌ Talend Studio not found at: `{talend_path}`\n\n"
                    "Please verify the path and try again, or use the manual guide above."
                )
            else:
                try:
                    with st.spinner("Running Talend migration engine..."):

                        workspace_path = os.path.join(temp_dir, "talend_workspace")

                        orchestrator = FullMigrationOrchestrator()
                        result = orchestrator.migrate(
                            talend_studio_path=talend_path,
                            repository_zip=zip_path,
                            workspace_path=workspace_path
                        )

                    st.success("✅ Migration pipeline completed")
                    st.json(result)

                    # Show CLI output details if available
                    check = result.get("migration_check") or {}
                    report = result.get("migration_report") or {}

                    if check.get("stdout") or check.get("stderr"):
                        with st.expander("📄 Migration Check Output"):
                            if check.get("stdout"):
                                st.code(check["stdout"], language="text")
                            if check.get("stderr"):
                                st.warning(check["stderr"])

                    if report.get("stdout") or report.get("stderr"):
                        with st.expander("📄 Migration Report Output"):
                            if report.get("stdout"):
                                st.code(report["stdout"], language="text")
                            if report.get("stderr"):
                                st.warning(report["stderr"])

                    launch = result.get("studio_launch") or {}
                    if launch.get("status") == "studio_launched":
                        st.info(
                            f"🖥️ Talend Studio launched (PID {launch.get('pid')}). "
                            "Complete the import inside Studio: "
                            "**File → Import → Talend Items**, select all items, click Finish."
                        )
                    elif launch.get("status") == "failed":
                        st.warning(
                            f"⚠️ Studio GUI launch failed: {launch.get('error')}\n\n"
                            "CLI migration commands ran — open Studio manually "
                            f"and point it to workspace: `{workspace_path}`"
                        )

                except FileNotFoundError as e:
                    st.error(f"❌ {e}")
                except Exception as e:
                    st.error(
                        f"❌ Automation failed: {e}\n\n"
                        "Use the manual import guide above instead."
                    )

    # ---------------------------------------------------
    # Context XMI Fix — Repair 'Contexts ctxCommon 0.1 was invalid'
    # ---------------------------------------------------

    section_header("Repair Import Errors")

    st.error(
        "**Getting an import error in Talend 8 Studio?**\n\n"
        "Upload your repository ZIP below to repair invalid XML character "
        "references, mismatched context `ItemState` references, and missing "
        "project registration descriptors."
    )

    fix_upload = st.file_uploader(
        "Upload Repository ZIP (to repair import errors)",
        type=["zip"],
        key="ctx_fix_upload"
    )

    if fix_upload:

        fix_temp = tempfile.mkdtemp()
        fix_input = os.path.join(fix_temp, "input.zip")
        fix_output = os.path.join(fix_temp, "FIXED_repository.zip")

        with open(fix_input, "wb") as f:
            f.write(fix_upload.read())

        with st.spinner("Scanning and repairing repository XML..."):
            result = fix_context_item_state_zip(fix_input, fix_output)

        if result["success"]:

            if result["fixes_applied"] == 0:
                st.success(
                    "No repairable XML or context reference issues found — "
                    "your ZIP is already clean. "
                    "The import error may have a different cause."
                )
            else:
                st.success(
                    f"Repaired **{result['fixes_applied']} file(s)**. "
                    "Download the fixed ZIP and re-import into Talend 8 Studio."
                )

                st.markdown("**Files repaired:**")
                for fix in result["xml_fix_details"]:
                    st.markdown(
                        f"- `{fix['file']}` — removed "
                        f"{fix['removed_references']} invalid XML reference(s)"
                    )
                for fix in result["fix_details"]:
                    st.markdown(f"- `{fix['file']}` — ItemState ID corrected")
                for fix in result["descriptor_fix_details"]:
                    st.markdown(
                        f"- `{fix['path']}` — added project registration files: "
                        f"`{', '.join(fix['created'])}`"
                    )

                with open(fix_output, "rb") as f:
                    st.download_button(
                        label="⬇️ Download FIXED Repository ZIP",
                        data=f,
                        file_name="FIXED_repository.zip",
                        mime="application/zip",
                        type="primary"
                    )

                st.info(
                    "**Next steps after download:**\n"
                    "1. In Talend 8 Studio: **File → Import → Talend Items**\n"
                    "2. Select the FIXED ZIP\n"
                    "3. Tick all items → click **Finish**\n"
                    "4. Retry the import"
                )
        else:
            st.error(
                f"Repair failed: {result.get('error', 'Unknown error')}\n\n"
                "Please check the ZIP is a valid Talend repository export."
            )

        shutil.rmtree(fix_temp, ignore_errors=True)

    # ---------------------------------------------------
    # NEW: Template-Based Talend 8 Repository Generation
    # ---------------------------------------------------

    section_header("Generate Target Repository")

    st.info(
        "**Template-Based Repository Reconstruction**\n\n"
        "This pipeline extracts jobs, contexts, routines, and metadata "
        "from your Open Studio ZIP and **regenerates them as native "
        "Talend 8 artifacts** — no XML patching, no context corruption.\n\n"
        "**Recommended:** upload your MIGRATIONTEMPLATE ZIP as the skeleton "
        "to guarantee Talend 8 project registration. Without it the tool "
        "auto-generates the skeleton (works but requires Talend to be lenient "
        "about project discovery).\n\n"
        "Download the output ZIP and import it into Talend 8 Studio "
        "via **File → Import → Talend Items**."
    )

    gen_upload = st.file_uploader(
        "① Upload your Open Studio Repository ZIP",
        type=["zip"],
        key="gen_upload"
    )

    skeleton_upload = st.file_uploader(
        "② Upload MIGRATIONTEMPLATE Skeleton ZIP (optional but strongly recommended)",
        type=["zip"],
        key="skeleton_upload",
        help=(
            "Export your MIGRATIONTEMPLATE project from Talend Studio "
            "(File → Export → Talend Items → select MIGRATIONTEMPLATE → ZIP). "
            "The builder will copy all skeleton files verbatim and only overlay "
            "context, metadata, process, and code with your migrated content. "
            "This fixes the 'project not visible in startup list' issue."
        )
    )

    if skeleton_upload:
        st.success("✅ Skeleton ZIP provided — Mode A (template copy) will be used")
    else:
        st.warning(
            "⚠️ No skeleton ZIP — Mode B (auto-generated skeleton) will be used. "
            "If the project does not appear in the Talend startup list, "
            "export MIGRATIONTEMPLATE and re-run with it uploaded above."
        )

    project_name = st.text_input(
        "Target Project Name",
        value="MigratedProject",
        key="gen_project_name",
        help="Name for the Talend 8 project folder inside the ZIP"
    )

    if gen_upload and st.button("🚀 Generate Talend 8 Repository", key="gen_btn", type="primary"):

        gen_temp = tempfile.mkdtemp(prefix="talend8_gen_")
        gen_input = os.path.join(gen_temp, "input.zip")
        gen_output = os.path.join(gen_temp, "migrated_repository.zip")
        gen_skeleton = None

        with open(gen_input, "wb") as f:
            f.write(gen_upload.read())

        if skeleton_upload:
            gen_skeleton = os.path.join(gen_temp, "skeleton.zip")
            with open(gen_skeleton, "wb") as f:
                f.write(skeleton_upload.read())

        progress = st.progress(0, text="Starting generation pipeline...")
        log_placeholder = st.empty()

        try:
            builder = Talend8RepositoryBuilder()

            progress.progress(10, text="Extracting source repository...")
            result = builder.build_from_zip(
                source_zip_path=gen_input,
                output_zip_path=gen_output,
                project_name=project_name.strip() or "MigratedProject",
                skeleton_zip_path=gen_skeleton,
            )

            progress.progress(100, text="Complete!")

            if result["success"]:
                stats = result["stats"]
                st.success(
                    f"✅ **Talend 8 repository generated successfully!**\n\n"
                    f"- **Jobs:** {stats['jobs_generated']}\n"
                    f"- **Contexts:** {stats['contexts_generated']}\n"
                    f"- **DB Connections:** {stats['connections_generated']}\n"
                    f"- **Routines:** {stats['routines_generated']}\n"
                    f"- **File Metadata:** {stats['file_metadata_generated']}\n"
                    f"- **Errors:** {len(stats['errors'])}"
                )

                if stats["errors"]:
                    with st.expander(f"⚠️ {len(stats['errors'])} non-fatal errors"):
                        for err in stats["errors"]:
                            st.markdown(f"- {err}")

                with open(gen_output, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Talend 8 Repository ZIP",
                        data=f,
                        file_name="migrated_repository.zip",
                        mime="application/zip",
                        type="primary",
                        key="gen_download_btn",
                    )

                mode_label = "Mode A (skeleton template)" if gen_skeleton else "Mode B (auto-generated skeleton)"
                st.info(
                    f"**Build mode:** {mode_label}\n\n"
                    "**Import into Talend 8 Studio:**\n"
                    "1. Create or open a target Talend 8 project\n"
                    "2. Inside the project, use **File → Import → Talend Items**\n"
                    f"3. Select `migrated_repository.zip`\n"
                    "4. Tick all items → click **Finish**\n\n"
                    "Do **not** use the startup-screen **Import an existing project** "
                    "option for this ZIP."
                )

                with st.expander("📋 Build Log"):
                    for line in result["log"]:
                        st.text(line)

            else:
                st.error(
                    f"❌ Generation failed: {result.get('error', 'Unknown error')}\n\n"
                    "Check that your ZIP is a valid Talend Open Studio export."
                )
                with st.expander("📋 Build Log"):
                    for line in result["log"]:
                        st.text(line)

        except Exception as e:
            st.error(f"❌ Unexpected error: {e}")

        finally:
            shutil.rmtree(gen_temp, ignore_errors=True)

    elif not gen_upload:
        st.caption("Upload a repository ZIP above to enable generation.")
