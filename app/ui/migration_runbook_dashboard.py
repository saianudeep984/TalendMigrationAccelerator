from __future__ import annotations

import json
from app.runbook import MigrationRunbookGenerator
from app.performance.cache_manager import get_cache_manager


def build_migration_runbook(jobs, upgrade=None):
    cache = get_cache_manager()
    fp = cache.fingerprint("migration_runbook", jobs, upgrade)
    return cache.cache_analysis(
        "migration_runbook",
        lambda: MigrationRunbookGenerator().generate(jobs, upgrade),
        fp,
    )


def export_runbook(runbook, fmt="json"):
    if (fmt or "json").lower() == "json":
        return json.dumps(runbook, indent=2, default=str)
    return MigrationRunbookGenerator().export(runbook, fmt)


def render_migration_runbook_dashboard(jobs=None, runbook=None):
    import streamlit as st
    from app.ui.design_system_v2 import std_page_header, section_header
    std_page_header("📋", "Migration Runbook", "Phased migration plan, waves and validation")
    runbook = runbook or st.session_state.get("migration_runbook")
    if runbook is None and jobs is not None:
        runbook = build_migration_runbook(jobs, st.session_state.get("upgrade_advisor"))
        st.session_state["migration_runbook"] = runbook
    if not runbook:
        st.info("Load a repository first.")
        return
    st.metric("Recommendation", runbook["migration_overview"]["recommendation"])
    section_header("Migration Plan"); st.json(runbook.get("migration_phases", []))
    section_header("Waves"); st.json(runbook.get("migration_waves", {}))
    section_header("Dependencies"); st.json(runbook.get("dependencies", {}))
    section_header("Risks"); st.dataframe(runbook.get("risks", []), width="stretch")
    section_header("Milestones"); st.json(runbook.get("executive_runbook", {}).get("milestones", []))
    section_header("Validation Tasks"); st.json(runbook.get("validation_steps", []))
    st.download_button("Export JSON", export_runbook(runbook, "json"), "migration_runbook.json")
    st.download_button("Export HTML", export_runbook(runbook, "html"), "migration_runbook.html")
    st.download_button("Export DOCX", export_runbook(runbook, "docx"), "migration_runbook.docx")


render = render_migration_runbook_dashboard


