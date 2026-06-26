import os

import streamlit as st

from app.tiap.documentation.report_pack_generator import (
    REPORT_PACK_FILENAME,
    REPORT_PACK_SESSION_KEY,
    build_report_pack,
)
from app.ai.repository_ai_context import REPOSITORY_AI_CONTEXT_SESSION_KEY
from app.tiap.documentation.template_manager import (
    CUSTOM_TEMPLATE_PATH,
    DEFAULT_TEMPLATE_PATH,
    TEMPLATE_SESSION_KEY,
    active_template_label,
    default_template_exists,
    restore_default_template,
    save_custom_template,
)
from app.ui.design_system import action_panel, hero, section


def render_ai_report_pack_generator() -> None:
    hero(
        "AI Report Pack Generator",
        "Generate a complete stakeholder-ready assessment from the latest repository analysis.",
        ["Complete DOCX/HTML/PDF/XLSX/JSON", "Flowcharts", "Readiness scores", "Migration recommendations"],
    )

    all_jobs = st.session_state.get("last_analysis_jobs")
    if not all_jobs:
        st.warning(
            "No repository analysis is available yet. Run Repository Intake first, then return here "
            "to generate the complete AI report pack."
        )
        return

    repo_path = st.session_state.get("last_repo_path")
    output_dir = "output"
    if TEMPLATE_SESSION_KEY not in st.session_state:
        st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH

    section("Pack Contents", "Generate the complete assessment DOCX from existing analysis outputs and the selected template.")
    cols = st.columns(3)
    items = [
        ("Executive Summary", "Leadership narrative and KPIs"),
        ("Repository Overview", "Portfolio inventory and job summary"),
        ("Readiness Scores", "Migration, cloud, documentation, and testing scores"),
        ("Flowcharts", "Technical, business, and repository flows"),
        ("Documentation", "Technical, functional, KT, and migration documentation"),
        ("Recommendations", "AI and remediation recommendations"),
    ]
    for col, (title, caption) in zip(cols * 2, items):
        with col:
            action_panel(title, caption, "Ready")

    section("Template Manager", "Choose the DOCX template used for placeholder replacement.")
    active_template = st.session_state.get(TEMPLATE_SESSION_KEY, DEFAULT_TEMPLATE_PATH)
    status_cols = st.columns(3)
    with status_cols[0]:
        if st.button("Use Default Template", width="stretch", key="rp_use_default_tmpl"):
            st.session_state[TEMPLATE_SESSION_KEY] = DEFAULT_TEMPLATE_PATH
            active_template = DEFAULT_TEMPLATE_PATH
    with status_cols[1]:
        if st.button("Restore Default Template", width="stretch", key="rp_restore_default_tmpl"):
            st.session_state[TEMPLATE_SESSION_KEY] = restore_default_template()
            active_template = st.session_state[TEMPLATE_SESSION_KEY]
    with status_cols[2]:
        default_status = "Available" if default_template_exists() else "Missing"
        action_panel("Active Template", active_template_label(active_template), default_status)

    uploaded_template = st.file_uploader(
        "Upload Custom Template",
        type=["docx"],
        key="report_pack_custom_template_upload",
    )
    if uploaded_template is not None:
        custom_path = save_custom_template(uploaded_template)
        st.session_state[TEMPLATE_SESSION_KEY] = custom_path
        active_template = custom_path
        st.success(f"Custom template uploaded to {CUSTOM_TEMPLATE_PATH}")

    if not default_template_exists():
        st.warning("Default template is missing. Add templates/default_template.docx before using the default option.")

    generated = st.session_state.get(REPORT_PACK_SESSION_KEY)
    if st.button("Generate Complete AI Pack", type="primary", width="stretch", key="rp_gen_pack"):
        with st.spinner("Generating complete AI report pack..."):
            generated = build_report_pack(
                all_jobs=all_jobs,
                repository_path=repo_path,
                output_dir=output_dir,
                effort=st.session_state.get("effort_estimate"),
                auto_fix_recs=st.session_state.get("auto_fix_recs"),
                technical_template=st.session_state.get("technical_doc_template"),
                report_template_path=active_template,
                test_cases=_format_test_cases(st.session_state.get("test_cases")),
                repository_ai_context=st.session_state.get(REPOSITORY_AI_CONTEXT_SESSION_KEY),
            )
            st.session_state[REPORT_PACK_SESSION_KEY] = generated
        st.success(f"Generated {REPORT_PACK_FILENAME}")

    if generated:
        docx_path = generated.get("docx_path")
        sections = generated.get("sections", {})
        template_result = generated.get("template_result", {})
        if template_result:
            replacements = template_result.get("replacement_count", 0)
            st.caption(f"Template placeholders replaced: {replacements}")
        st.markdown("### Generated Sections")
        st.dataframe(
            [{"Section": title, "Characters": len(str(content))} for title, content in sections.items()],
            width="stretch",
            hide_index=True,
        )

        if docx_path and os.path.exists(docx_path):
            with open(docx_path, "rb") as handle:
                st.download_button(
                    "Download Complete_Assessment.docx",
                    data=handle,
                    file_name=REPORT_PACK_FILENAME,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    width="stretch",
                )
        else:
            st.warning("The generated DOCX path is not available. Generate the pack again.")

        dl_cols = st.columns(4)
        html_path = generated.get("html_path")
        if html_path and os.path.exists(html_path):
            with open(html_path, "rb") as handle:
                dl_cols[0].download_button(
                    "Download .html",
                    data=handle,
                    file_name="Complete_Assessment.html",
                    mime="text/html",
                    width="stretch",
                )
        pdf_path = generated.get("pdf_path")
        if pdf_path and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as handle:
                dl_cols[1].download_button(
                    "Download .pdf",
                    data=handle,
                    file_name="Complete_Assessment.pdf",
                    mime="application/pdf",
                    width="stretch",
                )
        excel_path = generated.get("excel_path")
        if excel_path and os.path.exists(excel_path):
            with open(excel_path, "rb") as handle:
                dl_cols[2].download_button(
                    "Download .xlsx",
                    data=handle,
                    file_name="Complete_Assessment.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                )
        json_path = generated.get("json_path")
        if json_path and os.path.exists(json_path):
            with open(json_path, "rb") as handle:
                dl_cols[3].download_button(
                    "Download .json",
                    data=handle,
                    file_name="Complete_Assessment.json",
                    mime="application/json",
                    width="stretch",
                )


def _format_test_cases(test_cases) -> str:
    if not test_cases:
        return ""
    if isinstance(test_cases, str):
        return test_cases
    lines = []
    for item in test_cases:
        if isinstance(item, dict):
            tc_id = item.get("tc_id") or item.get("id") or "Test Case"
            category = item.get("category") or item.get("test_type") or ""
            objective = item.get("objective") or item.get("expected_result") or ""
            lines.append(f"- {tc_id} {category}: {objective}".strip())
        else:
            lines.append(f"- {item}")
    return "\n".join(lines)