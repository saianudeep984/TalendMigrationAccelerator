"""
TMA – Testing Architecture Page
Expandable sections: Unit Tests | Validation SQL | Reconciliation Rules | Src vs Tgt
"""
import streamlit as st
import pandas as pd
from app.tiap.testing.testing_architecture import build_testing_architecture


def _priority_badge(p: str) -> str:
    colors = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    return f"{colors.get(p, '⚪')} {p}"


def _severity_badge(s: str) -> str:
    return _priority_badge(s)


def render_testing_architecture_page(job_data: dict):
    st.header("🧪 Testing Architecture")
    st.caption(f"Job: **{job_data.get('job_name', 'Unknown')}**")

    arch = build_testing_architecture(job_data)

    # ── Unit Tests ────────────────────────────────────────────────────────────
    with st.expander(f"🔬 Unit Tests ({len(arch['unit_tests'])})", expanded=True):
        for tc in arch["unit_tests"]:
            with st.expander(f"{_priority_badge(tc['priority'])}  {tc['tc_id']} — {tc['type']}", expanded=False):
                st.markdown(f"**Component:** `{tc['component']}`")
                st.markdown(f"**Objective:** {tc['objective']}")
                st.markdown("**Steps:**")
                for s in tc["steps"]:
                    st.markdown(f"- {s}")
                st.success(f"✅ Expected: {tc['expected']}")

    # ── Validation SQL ────────────────────────────────────────────────────────
    with st.expander(f"🗄️ Validation SQL ({len(arch['validation_sql'])})", expanded=False):
        by_table: dict = {}
        for row in arch["validation_sql"]:
            by_table.setdefault(row["table"], []).append(row)
        for tbl, rows in by_table.items():
            with st.expander(f"📋 {tbl}", expanded=False):
                for r in rows:
                    st.markdown(f"**{r['type']}** — {r['description']}")
                    st.code(r["sql"], language="sql")

    # ── Reconciliation Rules ──────────────────────────────────────────────────
    with st.expander(f"⚖️ Reconciliation Rules ({len(arch['reconciliation_rules'])})", expanded=False):
        for rule in arch["reconciliation_rules"]:
            with st.expander(f"{_severity_badge(rule['severity'])}  {rule['rule_id']} — {rule['name']}", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Source:** `{rule['source']}`")
                    st.code(rule["sql_source"], language="sql")
                with col2:
                    st.markdown(f"**Target:** `{rule['target']}`")
                    st.code(rule["sql_target"], language="sql")
                st.info(f"🔍 Logic: `{rule['logic']}`  |  Tolerance: `{rule['tolerance']}`")

    # ── Source vs Target Validation ───────────────────────────────────────────
    with st.expander(f"🔀 Source vs Target Validation ({len(arch['src_vs_tgt'])})", expanded=False):
        for chk in arch["src_vs_tgt"]:
            with st.expander(f"📊 {chk['check_id']} — {chk['category']}", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Source Query:**")
                    st.code(chk["source_query"], language="sql")
                with col2:
                    st.markdown("**Target Query:**")
                    st.code(chk["target_query"], language="sql")
                st.success(f"✅ Pass Condition: {chk['pass_condition']}")
                st.error(f"❌ On Fail: {chk['on_fail']}")

    # ── Summary Table ─────────────────────────────────────────────────────────
    with st.expander("📈 Summary", expanded=False):
        st.dataframe(pd.DataFrame([
            {"Category": "Unit Tests",               "Count": len(arch["unit_tests"])},
            {"Category": "Validation SQL",           "Count": len(arch["validation_sql"])},
            {"Category": "Reconciliation Rules",     "Count": len(arch["reconciliation_rules"])},
            {"Category": "Src vs Tgt Checks",        "Count": len(arch["src_vs_tgt"])},
        ]), use_container_width=True, hide_index=True)
