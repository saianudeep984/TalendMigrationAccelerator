"""
AI Intelligence Hub
New Streamlit page providing:
  Tab 1 — AI Flowchart Generator
  Tab 2 — AI Documentation Generator
  Tab 3 — AI Test Case Generator
  Tab 4 — AI Migration Copilot
  Tab 5 — Routine Assessment
  Tab 6 — Joblet Assessment
  Tab 7 — Java Risk Assessment
  Tab 8 — Documentation Readiness Status
"""

import io
import html
import logging
import streamlit as st

from app.analyzers.readiness_scorer import score_to_rag as _score_to_rag

logger = logging.getLogger(__name__)

def _cloud_rag(cr: dict) -> str:
    """Get RAG status from a cloud_readiness dict (supports RAG status fields)."""
    if cr.get("rag") in ("RED", "AMBER", "GREEN"):
        return cr["rag"]
    return _score_to_rag(cr.get("score", 0))

import streamlit.components.v1 as components
import pandas as pd

from app.generators.ai_flowchart_generator import (
    generate_technical_flowchart,
    generate_business_flowchart,
    generate_parent_child_flowchart,
    generate_repository_flowchart,
)
from app.generators.ai_doc_generator import (
    generate_tech_doc,
    generate_functional_doc,
    generate_kt_doc,
    generate_migration_doc,
)
from app.generators.ai_test_generator import generate_test_cases
from app.analyzers.routine_analyzer import analyze_routines
from app.analyzers.joblet_analyzer import analyze_joblets
from app.analyzers.java_risk_analyzer import analyze_java_risks
from app.ai.llm_engine import ask_ollama
from app.ai.repository_ai_context import REPOSITORY_AI_CONTEXT_SESSION_KEY
from app.tiap.documentation.technical_doc_generator import TechnicalDocGenerator


def _render_mermaid_flowchart(mermaid: str, height: int = 520):
    components.html(
        """
        <div class="mermaid">
        {diagram}
        </div>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{
            startOnLoad: true,
            theme: 'base',
            themeVariables: {{
              primaryColor: '#FFFFFF',
              primaryBorderColor: '#6366F1',
              lineColor: '#7DD3FC',
              primaryTextColor: '#3F3F46',
              fontFamily: 'Arial'
            }}
          }});
        </script>
        """.format(diagram=html.escape(mermaid)),
        height=height,
        scrolling=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _badge(text, color):
    colors = {
        "RED":    "#e53e3e", "ORANGE": "#dd6b20",
        "YELLOW": "#d69e2e", "GREEN":  "#38a169",
        "BLUE":   "#3182ce", "GRAY":   "#718096",
    }
    bg = colors.get(color, "#718096")
    return (
        f'<span style="background:{bg};color:white;padding:2px 8px;'
        f'border-radius:12px;font-size:0.78rem;font-weight:600">{text}</span>'
    )


def _risk_color(risk: str) -> str:
    return {"CRITICAL": "RED", "HIGH": "ORANGE", "MEDIUM": "YELLOW", "LOW": "GREEN"}.get(
        str(risk).upper(), "GRAY"
    )


def _doc_readiness_score(all_jobs: list, session: dict) -> dict:
    """Compute Documentation + Testing readiness %"""
    total = len(all_jobs)
    if total == 0:
        return {"doc": 0, "test": 0, "overall": 0}

    generated_docs  = session.get("generated_docs_count",  0)
    generated_tests = session.get("generated_tests_count", 0)
    generated_fc    = session.get("generated_flowcharts_count", 0)

    doc_pct  = min(int((generated_docs  / total) * 100), 100)
    test_pct = min(int((generated_tests / total) * 100), 100)
    fc_pct   = min(int((generated_fc   / total) * 100), 100)
    overall  = int((doc_pct + test_pct + fc_pct) / 3)

    return {"doc": doc_pct, "test": test_pct, "flowchart": fc_pct, "overall": overall}


# ---------------------------------------------------------------------------
# Tab 1 — AI Flowchart Generator
# ---------------------------------------------------------------------------

def _render_flowcharts(all_jobs: list):
    st.header("📊 AI Flowchart Generator")
    st.caption(
        "Generate Technical, Business, Parent-Child and Repository flowcharts for any job."
    )

    job_names = [j["job_data"]["job_name"] for j in all_jobs]
    selected  = st.selectbox("Select Job", job_names, key="fc_job_select")
    job       = next(j for j in all_jobs if j["job_data"]["job_name"] == selected)
    if st.session_state.get("fc_selected_job") != selected:
        for key in ("fc_technical", "fc_technical_mermaid", "fc_business", "fc_parent_child"):
            st.session_state.pop(key, None)
        st.session_state["fc_selected_job"] = selected

    use_ai = st.checkbox("🤖 Use AI (Ollama) — falls back to rule-based if unavailable",
                         value=False, key="fc_use_ai")

    col_a, col_b = st.columns(2)

    with col_a:
        if st.button("⚡ Generate Technical Flowchart", key="fc_tech"):
            with st.spinner("Generating..."):
                fc = generate_technical_flowchart(job["job_data"], use_ai=use_ai)
                st.session_state["fc_technical"] = fc
                st.session_state["fc_technical_mermaid"] = TechnicalDocGenerator()._job_flowchart(job["job_data"])
                st.session_state.setdefault("generated_flowcharts_set", set()).add(selected)
                st.session_state["generated_flowcharts_count"] = len(
                    st.session_state.get("generated_flowcharts_set", set())
                )

        if st.button("💼 Generate Business Flowchart", key="fc_biz"):
            with st.spinner("Generating..."):
                fc = generate_business_flowchart(job["job_data"], use_ai=use_ai)
                st.session_state["fc_business"] = fc
                st.session_state.setdefault("generated_flowcharts_set", set()).add(selected)

    with col_b:
        if st.button("🌳 Generate Parent-Child Flowchart", key="fc_pc"):
            with st.spinner("Generating..."):
                fc = generate_parent_child_flowchart(job["job_data"], all_jobs)
                st.session_state["fc_parent_child"] = fc
                st.session_state.setdefault("generated_flowcharts_set", set()).add(selected)

        if st.button("🏭 Generate Repository Pipeline", key="fc_repo"):
            with st.spinner("Generating..."):
                st.session_state["fc_repository"] = generate_repository_flowchart()

    st.markdown("---")

    tabs = st.tabs(["🔧 Technical", "💼 Business", "🌳 Parent-Child", "🏭 Repository"])

    with tabs[0]:
        fc_tech = st.session_state.get("fc_technical")
        if isinstance(fc_tech, str):
            mermaid = st.session_state.get("fc_technical_mermaid") or TechnicalDocGenerator()._job_flowchart(job["job_data"])
            st.subheader("Visual Flowchart")
            _render_mermaid_flowchart(mermaid)
            with st.expander("Mermaid source", expanded=False):
                st.code(mermaid, language="mermaid")
            st.subheader("Generated Flowchart Text")
            st.code(fc_tech, language=None)
            st.download_button("📥 Download", fc_tech,
                               file_name=f"{selected}_technical_flowchart.txt",
                               mime="text/plain", key="dl_fc_tech")
        else:
            st.info("Click 'Generate Technical Flowchart' above.")

    with tabs[1]:
        fc_biz = st.session_state.get("fc_business")
        if isinstance(fc_biz, str):
            _biz_stripped = fc_biz.strip()
            _is_mermaid = _biz_stripped.startswith("graph ") or _biz_stripped.startswith("flowchart ")
            if _is_mermaid:
                _body_lines = [
                    l for l in _biz_stripped.splitlines()
                    if not l.strip().startswith("graph ")
                    and not l.strip().startswith("flowchart ")
                    and not l.strip().lower().startswith("style ")
                ]
                _mermaid_biz = "flowchart LR\n" + "\n".join(_body_lines)
            else:
                _lines = [l.strip() for l in _biz_stripped.splitlines() if l.strip() and not l.strip().startswith("=") and not l.strip().startswith("↓") and not l.strip().startswith("Business Flowchart")]
                _safe = [l.replace('"', "'") for l in _lines]
                _mermaid_biz = "flowchart TD\n" + "\n".join(f'    N{i}["{s}"]' + (f" --> N{i+1}" if i < len(_safe)-1 else "") for i, s in enumerate(_safe))
            _render_mermaid_flowchart(_mermaid_biz)
            st.download_button("📥 Download", fc_biz,
                               file_name=f"{selected}_business_flowchart.txt",
                               mime="text/plain", key="dl_fc_biz")
        else:
            st.info("Click 'Generate Business Flowchart' above.")

    with tabs[2]:
        fc_pc = st.session_state.get("fc_parent_child")
        if isinstance(fc_pc, str):
            st.code(fc_pc, language=None)
            st.download_button("📥 Download", fc_pc,
                               file_name=f"{selected}_parentchild_flowchart.txt",
                               mime="text/plain", key="dl_fc_pc")
        else:
            st.info("Click 'Generate Parent-Child Flowchart' above.")

    with tabs[3]:
        fc_repo = st.session_state.get("fc_repository")
        if isinstance(fc_repo, str):
            st.code(fc_repo, language=None)
            st.download_button("📥 Download", fc_repo,
                               file_name="repository_pipeline_flowchart.txt",
                               mime="text/plain", key="dl_fc_repo")
        else:
            st.info("Click 'Generate Repository Pipeline' above.")


# ---------------------------------------------------------------------------
# Tab 2 — AI Documentation Generator
# ---------------------------------------------------------------------------

def _render_docs(all_jobs: list):
    st.header("📄 AI Documentation Generator")
    st.caption(
        "Generate Technical, Functional, Knowledge Transfer, and Migration documents per job."
    )

    job_names = [j["job_data"]["job_name"] for j in all_jobs]
    selected  = st.selectbox("Select Job", job_names, key="doc_job_select")
    job       = next(j for j in all_jobs if j["job_data"]["job_name"] == selected)

    if st.session_state.get("doc_selected_job") != selected:
        for k in ["doc_tech_content","doc_func_content","doc_kt_content","doc_mig_content"]:
            st.session_state.pop(k, None)
        st.session_state["doc_selected_job"] = selected


    use_ai = st.checkbox("🤖 Use AI (Ollama)", value=False, key="doc_use_ai")

    # NOTE: document content is stored under "<type>_content" keys so they
    # never collide with the st.button widget keys (which store True/False).

    def _track(job_name):
        st.session_state.setdefault("generated_docs_set", set()).add(job_name)
        st.session_state["generated_docs_count"] = len(
            st.session_state["generated_docs_set"]
        )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📘 Generate Technical Doc", key="btn_doc_tech"):
            with st.spinner("Generating..."):
                _ctx = st.session_state.get(REPOSITORY_AI_CONTEXT_SESSION_KEY, {})
                st.session_state["doc_tech_content"] = _ctx.get("technical_documentation_notes") or generate_tech_doc(job["job_data"], use_ai=use_ai)
            st.session_state["doc_tech_job"] = selected
            _track(selected)

        if st.button("📗 Generate KT Document", key="btn_doc_kt"):
            with st.spinner("Generating..."):
                _ctx = st.session_state.get(REPOSITORY_AI_CONTEXT_SESSION_KEY, {})
                st.session_state["doc_kt_content"] = _ctx.get("kt_documentation_notes") or generate_kt_doc(job["job_data"], use_ai=use_ai)
                _track(selected)

    with col_b:
        if st.button("📙 Generate Functional Doc", key="btn_doc_func"):
            with st.spinner("Generating..."):
                _ctx = st.session_state.get(REPOSITORY_AI_CONTEXT_SESSION_KEY, {})
                st.session_state["doc_func_content"] = _ctx.get("functional_documentation_notes") or generate_functional_doc(job["job_data"], use_ai=use_ai)
            st.session_state["doc_func_job"] = selected
            _track(selected)

        if st.button("📕 Generate Migration Doc", key="btn_doc_mig"):
            with st.spinner("Generating..."):
                _ctx = st.session_state.get(REPOSITORY_AI_CONTEXT_SESSION_KEY, {})
                st.session_state["doc_mig_content"] = _ctx.get("migration_assessment") or generate_migration_doc(job["job_data"], use_ai=use_ai)
                _track(selected)

    # Bulk generate button
    if st.button("⚡ Generate All 4 Docs for This Job", key="btn_doc_all"):
        with st.spinner("Generating all documents..."):
            st.session_state["doc_tech_content"] = generate_tech_doc(job["job_data"], use_ai=use_ai)
            st.session_state["doc_tech_job"]=selected
            st.session_state["doc_func_content"] = generate_functional_doc(job["job_data"], use_ai=use_ai)
            st.session_state["doc_func_job"]=selected
            st.session_state["doc_kt_content"]   = generate_kt_doc(job["job_data"], use_ai=use_ai)
            st.session_state["doc_mig_content"]  = generate_migration_doc(job["job_data"], use_ai=use_ai)
            st.session_state["doc_kt_job"]=selected
            st.session_state["doc_mig_job"]=selected
            _track(selected)
            st.success("All 4 documents generated!")

    st.markdown("---")

    doc_tabs = st.tabs(["📘 Technical", "📙 Functional", "📗 KT Document", "📕 Migration"])

    def _show_doc(content_key, label, filename):
        content = st.session_state.get(content_key)
        # Guard: only show if it's actually a string (never a bool from a button widget)
        if isinstance(content, str):
            st.text_area(label, content, height=400, key=f"ta_{content_key}")
            st.download_button(
                f"📥 Download {label}", content,
                file_name=filename, mime="text/plain",
                key=f"dl_{content_key}"
            )
        else:
            st.info(f"Click 'Generate {label}' above.")

    with doc_tabs[0]:
        _show_doc("doc_tech_content", "Technical Documentation", f"{selected}_tech_doc.txt")
    with doc_tabs[1]:
        _show_doc("doc_func_content", "Functional Documentation", f"{selected}_functional_doc.txt")
    with doc_tabs[2]:
        _show_doc("doc_kt_content", "KT Document", f"{selected}_kt_doc.txt")
    with doc_tabs[3]:
        _show_doc("doc_mig_content", "Migration Documentation", f"{selected}_migration_doc.txt")


# ---------------------------------------------------------------------------
# Tab 3 — AI Test Case Generator
# ---------------------------------------------------------------------------

def _render_tests(all_jobs: list):
    st.header("🧪 AI Test Case Generator")
    st.caption("Generate structured test cases covering 7 categories per job.")

    job_names = [j["job_data"]["job_name"] for j in all_jobs]
    selected  = st.selectbox("Select Job", job_names, key="tc_job_select")
    job = next((j for j in all_jobs if j["job_data"]["job_name"] == selected), None)
    if job is None:
        st.error("Selected job not found")
        return

    col_a, col_b = st.columns([3, 1])
    with col_a:
        use_ai = st.checkbox("🤖 Use AI (Ollama)", value=False, key="tc_use_ai")
    with col_b:
        if st.button("⚡ Generate Test Cases", key="tc_gen"):
            with st.spinner("Generating test cases..."):
                cases = generate_test_cases(job["job_data"], use_ai=use_ai)
                st.session_state["test_cases"] = cases
                st.session_state["test_cases_job"] = selected
                st.session_state.setdefault("generated_tests_set", set()).add(selected)
                st.session_state["generated_tests_count"] = len(
                    st.session_state.get("generated_tests_set", set())
                )
                st.success(f"Generated {len(cases)} test cases!")

    if "test_cases" not in st.session_state:
        st.info("Select a job and click 'Generate Test Cases'.")
        return

    cases    = st.session_state["test_cases"]
    tc_job   = st.session_state.get("test_cases_job", "")

    priority_colors = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}

    for tc in cases:
        priority = tc.get("priority", "MEDIUM")
        icon     = priority_colors.get(priority, "🔵")
        with st.expander(f"{icon} {tc['tc_id']} — {tc['category']}", expanded=False):
            st.markdown(f"**Objective:** {tc['objective']}")
            st.markdown(f"**Priority:** {priority}")
            st.markdown("**Steps:**")
            for step in tc.get("steps", []):
                st.markdown(f"  {step}")
            st.markdown(f"**Expected Result:** {tc['expected_result']}")

    # Export to Excel
    if st.button("📥 Export Test Cases to Excel", key="tc_export"):
        rows = []
        for tc in cases:
            rows.append({
                "TC ID":           tc["tc_id"],
                "Category":        tc["category"],
                "Priority":        tc.get("priority", "MEDIUM"),
                "Objective":       tc["objective"],
                "Steps":           "\n".join(tc.get("steps", [])),
                "Expected Result": tc["expected_result"],
            })
        df  = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        buf.seek(0)
        st.download_button(
            "📥 Download Excel",
            data=buf,
            file_name=f"{tc_job}_test_cases.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="tc_dl_excel"
        )


# ---------------------------------------------------------------------------
# Tab 4 — AI Migration Copilot
# ---------------------------------------------------------------------------

_COPILOT_QUESTIONS = [
    "Which jobs are highest risk?",
    "Which jobs use custom routines?",
    "Which jobs are cloud blockers?",
    "What is the estimated migration effort?",
    "Show critical dependency chains.",
    "Why is readiness low?",
    "Which jobs use Oracle?",
    "Explain the repository structure.",
]


def _copilot_answer(question: str, all_jobs: list) -> str:
    """Rule-based copilot that answers repository-aware questions."""
    q = question.lower()

    total   = len(all_jobs)
    rs      = st.session_state.get("readiness_score", {})
    effort  = st.session_state.get("effort_estimate", {})

    # --- Highest risk ---
    if "highest risk" in q or "high risk" in q:
        high_risk = [
            j["job_data"]["job_name"]
            for j in all_jobs
            for r in j.get("enterprise_risk_report", [])
            if r.get("risk") in ("HIGH", "CRITICAL")
        ]
        unique = list(dict.fromkeys(high_risk))[:10]
        if unique:
            return "**Highest Risk Jobs:**\n" + "\n".join(f"• {j}" for j in unique)
        return "No high-risk jobs detected in this repository."

    # --- Custom routines ---
    if "custom routine" in q or "routine" in q:
        routine_data = st.session_state.get("routine_analysis", {})
        routines     = routine_data.get("routines", [])
        if routines:
            lines = ["**Custom Routines Detected:**"]
            for r in routines[:10]:
                lines.append(f"• {r['name']} — {r['risk_level']} risk, {r['job_count']} jobs")
            return "\n".join(lines)
        return "No custom routines detected. Run analysis in the Custom Routines tab."

    # --- Cloud blockers ---
    if "cloud blocker" in q or "cloud block" in q:
        blockers = [
            j["job_data"]["job_name"]
            for j in all_jobs
            if j.get("cloud_readiness", {}).get("readiness") == "LOW"
        ]
        if blockers:
            return (
                f"**{len(blockers)} Cloud Blockers Found:**\n"
                + "\n".join(f"• {j}" for j in blockers[:15])
            )
        return "No cloud blockers detected — all jobs have MEDIUM or HIGH cloud readiness."

    # --- Migration effort ---
    if "effort" in q or "how long" in q or "person day" in q or "week" in q:
        if effort:
            return (
                f"**Migration Effort Estimate:**\n"
                f"• Total Jobs: {total}\n"
                f"• Manual Jobs: {effort.get('manual_jobs', 0)}\n"
                f"• Auto-Migratable: {effort.get('auto_jobs', 0)}\n"
                f"• Estimated Hours: {effort.get('total_hours', 0)}\n"
                f"• Estimated Person-Days: {effort.get('estimated_days', 0)}\n"
                f"• Estimated Person-Weeks: {effort.get('person_weeks', 0):.1f}\n"
            )
        return "Run Repository Analysis first to get effort estimates."

    # --- Dependency chains ---
    if "dependency" in q or "critical chain" in q or "parent" in q:
        parent_child = [
            j["job_data"]["job_name"]
            for j in all_jobs
            if any(
                c.get("component_type") == "tRunJob"
                for c in j["job_data"].get("components", [])
            )
        ]
        if parent_child:
            return (
                f"**{len(parent_child)} Jobs with Child Job Dependencies:**\n"
                + "\n".join(f"• {j}" for j in parent_child[:15])
            )
        return "No parent-child job dependencies detected."

    # --- Readiness ---
    if "readiness" in q or "why" in q:
        if rs:
            lines = [
                f"**Migration Readiness: {rs.get('overall', 'RED')}**",
                f"• Component Compatibility: {rs.get('component_compatibility', 'RED')}",
                f"• Custom Component Risk: {rs.get('custom_component_risk', 'RED')}",
                f"• Cloud Readiness: {rs.get('cloud_readiness', 'RED')}",
                f"• Deprecated Component Risk: {rs.get('deprecated_component_risk', 'RED')}",
                f"• Dependency Complexity: {rs.get('dependency_complexity', 'RED')}",
            ]
            if rs.get("overall", "RED") != "GREEN":
                lines.append("\n**Main Issues Reducing Readiness:**")
                if rs.get("cloud_readiness", "RED") == "RED":
                    lines.append("• Cloud readiness is low — custom Java / file access detected.")
                if rs.get("custom_component_risk", "RED") == "RED":
                    lines.append("• Many custom components require manual migration.")
                if rs.get("deprecated_component_risk", "RED") == "RED":
                    lines.append("• Deprecated components need replacement before migration.")
            return "\n".join(lines)
        return "Run Repository Analysis to see readiness statuses."

    # --- Oracle jobs ---
    if "oracle" in q:
        oracle_jobs = [
            j["job_data"]["job_name"]
            for j in all_jobs
            if any(
                "Oracle" in c.get("component_type", "")
                for c in j["job_data"].get("components", [])
            )
        ]
        if oracle_jobs:
            return (
                f"**{len(oracle_jobs)} Jobs Using Oracle Components:**\n"
                + "\n".join(f"• {j}" for j in oracle_jobs[:15])
            )
        return "No Oracle components detected in this repository."

    # --- Repository structure ---
    if "structure" in q or "explain" in q or "overview" in q:
        component_counts = {}
        for j in all_jobs:
            for c in j["job_data"].get("components", []):
                ct = c.get("component_type", "")
                component_counts[ct] = component_counts.get(ct, 0) + 1
        top5 = sorted(component_counts.items(), key=lambda x: -x[1])[:5]
        lines = [
            f"**Repository Overview:**",
            f"• Total Jobs: {total}",
            f"• Migration Readiness: {rs.get('overall', 'N/A')}%",
            "\n**Top 5 Components by Usage:**",
        ]
        for comp, cnt in top5:
            lines.append(f"• {comp}: {cnt} uses")
        return "\n".join(lines)

    # --- AI fallback ---
    context = (
        f"Repository has {total} Talend jobs. "
        f"Migration Readiness: {rs.get('overall', 'N/A')}%. "
        f"Effort: {effort.get('person_weeks', 'N/A')} weeks."
    )
    try:
        return ask_ollama(
            f"You are a Talend migration expert. Context: {context}\n"
            f"Question: {question}\n"
            "Answer concisely."
        )
    except Exception:
        logger.exception("Failed to answer copilot question with AI; using fallback response.")
        return (
            f"I couldn't find a specific rule-based answer for: '{question}'.\n\n"
            "Try questions like:\n"
            "• Which jobs are highest risk?\n"
            "• What is the migration effort?\n"
            "• Which jobs are cloud blockers?\n"
            "• Which jobs use Oracle?\n"
            "Or configure Ollama for open-ended AI answers."
        )


def _render_copilot(all_jobs: list):
    st.header("🤖 AI Migration Copilot")
    st.caption("Ask repository-aware questions about your Talend migration.")

    # Quick question buttons
    st.markdown("**Quick Questions:**")
    cols = st.columns(4)
    for i, q in enumerate(_COPILOT_QUESTIONS):
        if cols[i % 4].button(q, key=f"copilot_q_{i}"):
            st.session_state["copilot_input"] = q

    st.markdown("---")

    # Free-text input
    user_q = st.text_input(
        "Ask anything about your repository:",
        placeholder="e.g. Which jobs use custom routines?",
        key="copilot_input",
    )

    if st.button("🚀 Ask Copilot", key="copilot_ask") and user_q.strip():
        with st.spinner("Analysing repository..."):
            answer = _copilot_answer(user_q, all_jobs)
        st.session_state["copilot_answer"] = answer
        st.session_state["copilot_question"] = user_q

    if "copilot_answer" in st.session_state:
        st.markdown("---")
        st.markdown(f"**Q: {st.session_state['copilot_question']}**")
        st.markdown(st.session_state["copilot_answer"])


# ---------------------------------------------------------------------------
# Tab 5 — Routine Assessment
# ---------------------------------------------------------------------------

def _render_routine_assessment(all_jobs: list, repo_path: str = None):
    st.header("☕ Custom Routine Assessment")
    st.caption("Java routines, libraries, and beans detected in the repository.")

    if "routine_analysis" not in st.session_state:
        if st.button("🔍 Analyze Routines", key="ra_btn"):
            with st.spinner("Scanning routines..."):
                result = analyze_routines(all_jobs, repo_path=repo_path)
                st.session_state["routine_analysis"] = result
        else:
            st.info("Click 'Analyze Routines' to scan the repository.")
            return

    data = st.session_state["routine_analysis"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Routines",      data["total_routines"])
    c2.metric("High Risk",           data["high_risk_count"])
    c3.metric("Jobs Impacted",       data["total_jobs_impacted"])

    st.markdown("---")

    if not data["routines"]:
        st.info("No custom routines detected. (Routines folder may be empty or not present.)")
        return

    rows = []
    for r in data["routines"]:
        rows.append({
            "Routine Name":    r["name"],
            "Lines of Code":   r["lines_of_code"] or "N/A",
            "Jobs Using":      r["job_count"],
            "Cloud Compatible": r["cloud_compatible"],
            "Risk Level":      r["risk_level"],
            "Risks Detected":  ", ".join(r["risks"]),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)

    # Detail expanders
    for r in data["routines"]:
        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(r["risk_level"], "⚪")
        with st.expander(f"{risk_icon} {r['name']} — {r['risk_level']} Risk", expanded=False):
            st.markdown(f"**Lines of Code:** {r['lines_of_code'] or 'N/A'}")
            st.markdown(f"**Cloud Compatible:** {r['cloud_compatible']}")
            st.markdown(f"**Risks:** {', '.join(r['risks'])}")
            if r["jobs_using"]:
                st.markdown(f"**Jobs Using This Routine ({r['job_count']}):**")
                for j in r["jobs_using"][:20]:
                    st.markdown(f"  • {j}")


# ---------------------------------------------------------------------------
# Tab 6 — Joblet Assessment
# ---------------------------------------------------------------------------

def _render_joblet_assessment(all_jobs: list, repo_path: str = None):
    st.header("🔗 Joblet Assessment")
    st.caption("Reusable Talend joblets and their impact across the repository.")

    if "joblet_analysis" not in st.session_state:
        if st.button("🔍 Analyze Joblets", key="ja_btn"):
            with st.spinner("Scanning joblets..."):
                result = analyze_joblets(all_jobs, repo_path=repo_path)
                st.session_state["joblet_analysis"] = result
        else:
            st.info("Click 'Analyze Joblets' to scan the repository.")
            return

    data = st.session_state["joblet_analysis"]

    c1, c2 = st.columns(2)
    c1.metric("Total Joblets",       data["total_joblets"])
    c2.metric("Jobs Impacted",       data["total_jobs_impacted"])

    st.markdown("---")

    if not data["joblets"]:
        st.info("No joblets detected in this repository.")
        return

    rows = []
    for j in data["joblets"]:
        rows.append({
            "Joblet Name":  j["name"],
            "Jobs Using":   j["job_count"],
            "Impact Status": j["risk_level"],
            "Risk Level":   j["risk_level"],
            "Source":       j["source"],
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)

    for jlet in data["joblets"][:10]:
        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(jlet["risk_level"], "⚪")
        with st.expander(f"{risk_icon} {jlet['name']} - Impact {jlet['risk_level']}", expanded=False):
            st.markdown(f"**Jobs Using ({jlet['job_count']}):**")
            for j in jlet["jobs_using"][:15]:
                st.markdown(f"  • {j}")


# ---------------------------------------------------------------------------
# Tab 7 — Java Risk Assessment
# ---------------------------------------------------------------------------

def _render_java_risk_assessment(all_jobs: list):
    st.header("☕ Java Risk Assessment")
    st.caption("Detects tJava / tJavaRow / tJavaFlex components and associated cloud risks.")

    if "java_risk_analysis" not in st.session_state:
        with st.spinner("Scanning Java components..."):
            result = analyze_java_risks(all_jobs)
            st.session_state["java_risk_analysis"] = result

    data = st.session_state["java_risk_analysis"]
    summ = data["summary"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Java Jobs",   summ["total_java_jobs"])
    c2.metric("🔴 Critical", summ["critical"])
    c3.metric("🟠 High",     summ["high"])
    c4.metric("🟡 Medium",   summ["medium"])
    c5.metric("Java Risk Status", "RED" if summ["critical"] or summ["high"] else ("AMBER" if summ["medium"] else "GREEN"))

    st.markdown("---")

    if not data["job_risks"]:
        st.success("✅ No inline Java components detected — good cloud readiness!")
        return

    rows = []
    for r in data["job_risks"]:
        rows.append({
            "Job Name":        r["job_name"],
            "Java Components": ", ".join(r["java_components"]),
            "Count":           r["java_count"],
            "File Access":     "⚠️ Yes" if r["flags"]["file_access"]     else "No",
            "Runtime Exec":    "🔴 Yes" if r["flags"]["runtime_exec"]    else "No",
            "Unsupported API": "⚠️ Yes" if r["flags"]["unsupported_api"] else "No",
            "Cloud Risk":      "⚠️ Yes" if r["flags"]["cloud_risk"]      else "No",
            "Risk Level":      r["risk_level"],
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


# ---------------------------------------------------------------------------
# Tab 8 — Documentation Readiness Status
# ---------------------------------------------------------------------------

def _render_doc_readiness_score(all_jobs: list):
    st.header("📋 Documentation & Testing Readiness Status")
    st.caption(
        "Tracks how many jobs have been documented, have flowcharts, and have test cases generated."
    )

    total   = len(all_jobs)
    scores  = _doc_readiness_score(all_jobs, st.session_state)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documentation", "GREEN" if scores["doc"] >= 70 else ("AMBER" if scores["doc"] >= 40 else "RED"))
    c2.metric("Testing", "GREEN" if scores["test"] >= 70 else ("AMBER" if scores["test"] >= 40 else "RED"))
    c3.metric("Flowcharts", "GREEN" if scores.get("flowchart", 0) >= 70 else ("AMBER" if scores.get("flowchart", 0) >= 40 else "RED"))
    c4.metric("Overall", "GREEN" if scores["overall"] >= 70 else ("AMBER" if scores["overall"] >= 40 else "RED"))

    st.markdown("---")

    generated_docs = st.session_state.get("generated_docs_set",       set())
    generated_fc   = st.session_state.get("generated_flowcharts_set", set())
    generated_tc   = st.session_state.get("generated_tests_set",      set())

    rows = []
    for j in all_jobs:
        jname = j["job_data"]["job_name"]
        rows.append({
            "Job Name":         jname,
            "Documentation":    "✅" if jname in generated_docs else "❌",
            "Flowchart":        "✅" if jname in generated_fc   else "❌",
            "Test Cases":       "✅" if jname in generated_tc   else "❌",
            "Ready":            "✅" if (jname in generated_docs and
                                         jname in generated_fc and
                                         jname in generated_tc) else "⚠️",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)

    # Tips
    missing_docs = total - scores["doc"] * total // 100
    if missing_docs > 0:
        st.info(
            f"💡 {missing_docs} jobs still need documentation. "
            "Go to the **AI Documentation Generator** tab and use 'Bulk Generate' for quick coverage."
        )


# ---------------------------------------------------------------------------
# Master render function
# ---------------------------------------------------------------------------

def render_ai_intelligence_hub(all_jobs: list, repo_path: str = None):
    """Entry point called from streamlit_app.py"""
    if not all_jobs:
        st.warning(
            "⚠️ **No analysis data found.**\n\n"
            "Go to **🏠 Repository Analysis** first, upload your repository ZIP and run analysis."
        )
        return

    st.markdown("## 🧠 AI Intelligence Hub")
    st.caption(
        "AI-powered Flowcharts · Documentation · Test Cases · Migration Copilot · "
        "Routine / Joblet / Java Risk Assessment"
    )

    tabs = st.tabs([
        "📊 Flowcharts",
        "📄 Documentation",
        "🧪 Test Cases",
        "🤖 Migration Copilot",
        "☕ Routines",
        "🔗 Joblets",
        "📋 Doc Readiness",
        "🔥 Java Risk",
    ])

    with tabs[0]:
        _render_flowcharts(all_jobs)
    with tabs[1]:
        _render_docs(all_jobs)
    with tabs[2]:
        _render_tests(all_jobs)
    with tabs[3]:
        _render_copilot(all_jobs)
    with tabs[4]:
        _render_routine_assessment(all_jobs, repo_path=repo_path)
    with tabs[5]:
        _render_joblet_assessment(all_jobs, repo_path=repo_path)
    with tabs[6]:
        _render_doc_readiness_score(all_jobs)
    with tabs[7]:
        _render_java_risk_assessment(all_jobs)
