"""
Technical Design Document (TDD) Page
Executive Summary: fully populated from session-state metadata + AI generation.
All other sections: placeholders.
"""
import os
import re
import pandas as pd
import streamlit as st
from app.ui.design_system_v2 import page_header

# Module-level key context — set by callers before invoking section renderers
# so that all widget keys are unique when the page is embedded in another page.
_KEY_CTX: str = ""
from app.parser.source_target_extractor import build_source_target_inventory
from app.tiap.documentation import tdd_sections
from app.tiap.documentation.tdd_export import export_tdd, _safe_job_name
from app.tiap.testing.testing_architecture import build_testing_architecture
from app.tiap.migration_assessment.migration_assessment import build_migration_assessment
from app.tiap.exec_summary.exec_summary import build_executive_summary

_API_TYPE_RE = re.compile(r"REST|SOAP|HTTP|WebService|API|Salesforce|Kafka|MQ", re.I)


# ── helpers ──────────────────────────────────────────────────────────────────

def _rag_badge(rag: str) -> str:
    color = {"GREEN": "#16a34a", "AMBER": "#d97706", "RED": "#dc2626"}.get(rag, "#64748b")
    return (
        f'<span style="background:{color};color:#fff;font-size:11px;font-weight:700;'
        f'padding:2px 10px;border-radius:20px;">{rag}</span>'
    )


def _infer_job_type(components: list) -> str:
    types = {c.get("component_type", "") for c in components}
    has_input  = any(t.endswith("Input")  or "tRowGenerator" in t for t in types)
    has_output = any(t.endswith("Output") for t in types)
    has_map    = any("tMap" in t for t in types)
    has_sql    = any(t.endswith("Row") or "tRunJob" in t for t in types)
    if has_sql and not has_map:
        return "SQL Execution"
    if has_input and has_output and has_map:
        return "ETL Transformation"
    if has_input and has_output:
        return "Data Movement"
    if "tRunJob" in types:
        return "Orchestration / Master Job"
    if has_input:
        return "Data Extraction"
    if has_output:
        return "Data Load"
    return "Utility / Processing"


def _count_sources_targets(components: list):
    sources = [c for c in components if c.get("component_type", "").endswith("Input")
               or c.get("component_type", "") == "tRowGenerator"]
    targets = [c for c in components if c.get("component_type", "").endswith("Output")]
    return len(sources), len(targets)


def _classify_components(components: list):
    """Split already-extracted component_type strings into joblets vs standard
    Talend components. Standard components follow the tXxx naming convention;
    instantiated joblets surface under their own class name. No XML is parsed
    here — this only re-classifies component metadata already extracted."""
    joblets, standard = set(), set()
    for c in components:
        ctype = c.get("component_type", "")
        if not ctype:
            continue
        if re.match(r"^t[A-Z]", ctype):
            standard.add(ctype)
        else:
            joblets.add(ctype)
    return sorted(joblets), sorted(standard)


def _external_libraries_for_job(job: dict) -> list:
    """Best-effort listing of .jar files already present alongside the job's
    exported/extracted location (job folder + sibling lib/ folder). This reads
    the filesystem only — it does not open or parse any job XML."""
    libs = set()
    file_path = job.get("file_path", "")
    if not file_path:
        return []
    job_dir = os.path.dirname(file_path)
    candidate_dirs = [job_dir, os.path.dirname(job_dir),
                      os.path.join(os.path.dirname(job_dir), "lib")]
    for d in candidate_dirs:
        if d and os.path.isdir(d):
            try:
                for f in os.listdir(d):
                    if f.lower().endswith(".jar"):
                        libs.add(f)
            except OSError:
                pass
    return sorted(libs)


_PIPELINE_STAGES = ["Source", "Validation", "Transformation", "Enrichment", "Error Handling", "Target"]

_STAGE_RULES = [
    ("Error Handling", re.compile(r"Die|Warn|LogCatcher|StatCatcher|Reject|ErrorCatcher", re.I)),
    ("Validation",      re.compile(r"SchemaCompliance|Assert|FilterRow|RuleSurvivorship|DataValidation|tFilter", re.I)),
    ("Enrichment",      re.compile(r"Normalize|Denormalize|Replace|FuzzyMatch|Join|Lookup|Enrich", re.I)),
    ("Source",          re.compile(r"Input$|tRowGenerator|tFileInput|tDBInput|.*Input.*", re.I)),
    ("Target",          re.compile(r"Output$|.*Output.*", re.I)),
    ("Transformation",  re.compile(r"Map|Aggregate|Pivot|Unpivot|Sort|Convert|RunJob", re.I)),
]


def _classify_pipeline_stage(component_type: str) -> str:
    """Map an already-parsed component_type string to a pipeline stage.
    Pure pattern classification over existing metadata — no XML re-parsing."""
    for stage, pattern in _STAGE_RULES:
        if pattern.search(component_type or ""):
            return stage
    return "Transformation"


def _render_pipeline_diagram(all_jobs: list):
    """High-Level Architecture Diagram: Source → Validation → Transformation →
    Enrichment → Error Handling → Target, auto-built from already-parsed
    component metadata across the loaded repository."""
    stage_counts = {s: 0 for s in _PIPELINE_STAGES}
    stage_components = {s: set() for s in _PIPELINE_STAGES}
    for j in all_jobs:
        for c in j["job_data"].get("components", []):
            ctype = c.get("component_type", "")
            stage = _classify_pipeline_stage(ctype)
            stage_counts[stage] += 1
            stage_components[stage].add(ctype)

    dot = ['digraph G {', 'rankdir=LR; node[shape=box,style=filled,fontsize=12,'
           'fontname="Arial",fontcolor="white",color="none",width=1.6];']
    colors = {"Source": "#0ea5e9", "Validation": "#f59e0b", "Transformation": "#6366f1",
              "Enrichment": "#10b981", "Error Handling": "#dc2626", "Target": "#64748b"}
    for s in _PIPELINE_STAGES:
        label = f"{s}\\n({stage_counts[s]} components)"
        dot.append(f'"{s}" [label="{label}",fillcolor="{colors[s]}"];')
    for a, b in zip(_PIPELINE_STAGES[:-1], _PIPELINE_STAGES[1:]):
        dot.append(f'"{a}" -> "{b}";')
    dot.append("}")
    st.graphviz_chart("\n".join(dot))

    with st.expander("Component mapping per stage"):
        for s in _PIPELINE_STAGES:
            comps = ", ".join(sorted(stage_components[s])) or "—"
            st.markdown(f"**{s}**: {comps}")


def _ai_generate(prompt: str) -> str:
    """Call Ollama llm_engine (rule-based fallback if unavailable)."""
    try:
        from app.ai.llm_engine import LLMEngine
        engine = LLMEngine()
        return engine.generate(prompt)
    except Exception:
        return "(AI unavailable — connect Ollama to generate this section.)"


def _build_business_prompt(meta: dict) -> str:
    return (
        f"You are a senior data architect documenting a Talend ETL job.\n"
        f"Job Name: {meta['job_name']}\n"
        f"Job Type: {meta['job_type']}\n"
        f"Component Count: {meta['component_count']}\n"
        f"Source Count: {meta['source_count']}, Target Count: {meta['target_count']}\n"
        f"Complexity: {meta['complexity_level']} (score {meta['complexity_score']})\n"
        f"Write a 3–4 sentence BUSINESS description of what this job likely does, "
        f"its business value, and who would use it. Plain English, no bullet points."
    )


def _build_technical_prompt(meta: dict) -> str:
    comps = ", ".join(meta.get("sample_components", [])) or "N/A"
    return (
        f"You are a senior data architect documenting a Talend ETL job.\n"
        f"Job Name: {meta['job_name']}\n"
        f"Job Type: {meta['job_type']}\n"
        f"Key Components (sample): {comps}\n"
        f"Component Count: {meta['component_count']}, Sources: {meta['source_count']}, Targets: {meta['target_count']}\n"
        f"Complexity: {meta['complexity_level']} (score {meta['complexity_score']})\n"
        f"Migration Readiness RAG: {meta['readiness_rag']}\n"
        f"Write a 3–4 sentence TECHNICAL description covering the data flow, "
        f"key Talend components used, and any notable complexity or risk. No bullet points."
    )


# ── section renderers ─────────────────────────────────────────────────────────

def _render_executive_summary():
    all_jobs = st.session_state.get("last_analysis_jobs", [])

    if not all_jobs:
        st.info("⬜ No repository loaded. Upload and analyse a Talend repository to populate this section.")
        return

    # ── Job selector ─────────────────────────────────────────────────────────
    job_names = [j["job_data"].get("job_name", "—") for j in all_jobs]
    selected = st.selectbox("Select Job", job_names, key=f"tdd_exec_job_sel{_KEY_CTX}")
    job = next((j for j in all_jobs if j["job_data"].get("job_name") == selected), all_jobs[0])

    jd         = job["job_data"]
    components = jd.get("components", [])
    complexity = job.get("complexity", {})
    cr         = job.get("cloud_readiness", {})

    job_name        = jd.get("job_name", "—")
    job_type        = _infer_job_type(components)
    component_count = len(components)
    source_count, target_count = _count_sources_targets(components)
    complexity_score  = complexity.get("score", "—")
    complexity_level  = complexity.get("complexity") or complexity.get("level", "—")
    readiness_rag     = cr.get("rag", "—")
    talend_version    = jd.get("talend_version", "—")
    sample_components = list({c.get("component_type", "") for c in components})[:6]

    meta = {
        "job_name": job_name, "job_type": job_type,
        "component_count": component_count, "source_count": source_count,
        "target_count": target_count, "complexity_score": complexity_score,
        "complexity_level": complexity_level, "readiness_rag": readiness_rag,
        "sample_components": sample_components,
    }

    # ── KPI strip ────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Job Name",          job_name[:18] + "…" if len(job_name) > 18 else job_name)
    k2.metric("Job Type",          job_type)
    k3.metric("Complexity",        f"{complexity_level} ({complexity_score})")
    k4.metric("Components",        component_count)
    k5.metric("Sources / Targets", f"{source_count} / {target_count}")
    k6.metric("Talend Version",    talend_version)

    st.divider()

    # ── Detail card ──────────────────────────────────────────────────────────
    rag_html = _rag_badge(readiness_rag)
    st.markdown(
        f"""
        <div style="border:1px solid #e2e8f0;border-radius:10px;padding:18px 22px;background:#f8fafc;margin-bottom:14px;">
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <tr>
                    <td style="padding:5px 12px 5px 0;color:#64748b;width:160px;">Job Name</td>
                    <td style="padding:5px 0;font-weight:600;color:#0f172a;">{job_name}</td>
                    <td style="padding:5px 12px 5px 24px;color:#64748b;width:160px;">Job Type</td>
                    <td style="padding:5px 0;font-weight:600;color:#0f172a;">{job_type}</td>
                </tr>
                <tr>
                    <td style="padding:5px 12px 5px 0;color:#64748b;">Purpose</td>
                    <td style="padding:5px 0;color:#0f172a;">Derived from component analysis</td>
                    <td style="padding:5px 12px 5px 24px;color:#64748b;">Owner</td>
                    <td style="padding:5px 0;color:#0f172a;">—</td>
                </tr>
                <tr>
                    <td style="padding:5px 12px 5px 0;color:#64748b;">Complexity Score</td>
                    <td style="padding:5px 0;font-weight:600;color:#0f172a;">{complexity_level} ({complexity_score})</td>
                    <td style="padding:5px 12px 5px 24px;color:#64748b;">Component Count</td>
                    <td style="padding:5px 0;font-weight:600;color:#0f172a;">{component_count}</td>
                </tr>
                <tr>
                    <td style="padding:5px 12px 5px 0;color:#64748b;">Source Count</td>
                    <td style="padding:5px 0;font-weight:600;color:#0f172a;">{source_count}</td>
                    <td style="padding:5px 12px 5px 24px;color:#64748b;">Target Count</td>
                    <td style="padding:5px 0;font-weight:600;color:#0f172a;">{target_count}</td>
                </tr>
                <tr>
                    <td style="padding:5px 12px 5px 0;color:#64748b;">Migration Readiness</td>
                    <td style="padding:5px 0;">{rag_html}</td>
                    <td style="padding:5px 12px 5px 24px;color:#64748b;">Talend Version</td>
                    <td style="padding:5px 0;color:#0f172a;">{talend_version}</td>
                </tr>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── AI Generation ────────────────────────────────────────────────────────
    st.markdown("#### 🤖 AI-Generated Descriptions")
    col_b, col_t = st.columns(2)

    biz_key  = f"tdd_biz_desc_{job_name}"
    tech_key = f"tdd_tech_desc_{job_name}"

    with col_b:
        st.markdown("**Business Description**")
        if st.button("Generate Business Description", key=f"tdd_gen_biz_{job_name}{_KEY_CTX}"):
            with st.spinner("Generating…"):
                st.session_state[biz_key] = _ai_generate(_build_business_prompt(meta))
        if biz_key in st.session_state:
            st.text_area("", value=st.session_state[biz_key], height=160,
                         key=f"tdd_biz_ta_{job_name}{_KEY_CTX}", label_visibility="collapsed")
        else:
            st.markdown(
                '<div style="border:1px dashed #cbd5e1;border-radius:8px;padding:16px;'
                'color:#94a3b8;font-size:13px;min-height:80px;">Click ↑ to generate</div>',
                unsafe_allow_html=True,
            )

    with col_t:
        st.markdown("**Technical Description**")
        if st.button("Generate Technical Description", key=f"tdd_gen_tech_{job_name}{_KEY_CTX}"):
            with st.spinner("Generating…"):
                st.session_state[tech_key] = _ai_generate(_build_technical_prompt(meta))
        if tech_key in st.session_state:
            st.text_area("", value=st.session_state[tech_key], height=160,
                         key=f"tdd_tech_ta_{job_name}{_KEY_CTX}", label_visibility="collapsed")
        else:
            st.markdown(
                '<div style="border:1px dashed #cbd5e1;border-radius:8px;padding:16px;'
                'color:#94a3b8;font-size:13px;min-height:80px;">Click ↑ to generate</div>',
                unsafe_allow_html=True,
            )


# ── Job Architecture ──────────────────────────────────────────────────────────

def _render_architecture():
    all_jobs = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        st.info("⬜ No repository loaded. Upload and analyse a Talend repository to populate this section.")
        return

    # ── aggregate existing per-job metadata (no re-parsing) ────────────────────
    job_names = {j["job_data"].get("job_name", "—") for j in all_jobs}
    orchestrators, edges, all_routines, all_joblets, all_libs = set(), [], set(), set(), set()
    for j in all_jobs:
        dep, jd = j.get("dependencies", {}), j["job_data"]
        name = jd.get("job_name", "—")
        if dep.get("child_jobs"):
            orchestrators.add(name)
        for c in dep.get("child_jobs", []):
            edges.append((name, c))
        all_routines.update(r for r in dep.get("routines", []) if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", r or ""))
        joblets, _ = _classify_components(jd.get("components", []))
        all_joblets.update(joblets)
        all_libs.update(_external_libraries_for_job(j))
    leaf_jobs = job_names - orchestrators

    # ── High-Level Architecture ─────────────────────────────────────────────────
    st.markdown("#### 🏗️ High-Level Architecture")
    _render_pipeline_diagram(all_jobs)
    st.divider()
    st.markdown("##### Job Orchestration Hierarchy")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Jobs", len(job_names))
    k2.metric("Parent / Orchestrator Jobs", len(orchestrators))
    k3.metric("Child / Leaf Jobs", len(leaf_jobs))
    k4.metric("Joblets in Use", len(all_joblets))
    k5.metric("Routines in Use", len(all_routines))

    if edges:
        dot = ['digraph G {', 'rankdir=TB; node[shape=box,style=filled,fontsize=11,fontname="Arial",fontcolor="white",color="none"];']
        for n in job_names:
            dot.append(f'"{n}" [fillcolor="{"#6366f1" if n in orchestrators else "#94a3b8"}"];')
        for s, t in edges:
            dot.append(f'"{s}" -> "{t}";')
        dot.append("}")
        st.graphviz_chart("\n".join(dot))
    else:
        st.caption("No parent → child (tRunJob) relationships found across the loaded repository.")

    st.divider()

    # ── Detailed Architecture ───────────────────────────────────────────────────
    st.markdown("#### 🔍 Detailed Architecture")
    selected = st.selectbox("Select Job", sorted(job_names), key=f"tdd_arch_job_sel{_KEY_CTX}")
    job = next((j for j in all_jobs if j["job_data"].get("job_name") == selected), all_jobs[0])
    jd, dep = job["job_data"], job.get("dependencies", {})
    joblets, _ = _classify_components(jd.get("components", []))
    libs = _external_libraries_for_job(job)
    routines = sorted({r for r in dep.get("routines", []) if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", r or "")})
    ctx_vars = sorted({c for c in dep.get("contexts", []) if isinstance(c, str) and c.startswith("context.")})

    def _table(rows, col):
        if rows:
            st.dataframe(pd.DataFrame({col: rows}), use_container_width=True, hide_index=True)
        else:
            st.caption(f"No {col.lower()} identified for this job.")

    tabs = st.tabs(["Parent Jobs", "Child Jobs", "Joblets", "Context Groups", "Routines", "External Libraries"])
    with tabs[0]:
        _table(dep.get("parent_jobs", []), "Parent Job")
    with tabs[1]:
        _table(dep.get("child_jobs", []), "Child Job")
    with tabs[2]:
        _table(joblets, "Joblet")
    with tabs[3]:
        if ctx_vars:
            st.markdown("**Context Group: `Default`**")
            st.dataframe(pd.DataFrame({"Context Variable": ctx_vars}), use_container_width=True, hide_index=True)
        else:
            st.caption("No context-group variables identified for this job.")
    with tabs[4]:
        _table(routines, "Routine")
    with tabs[5]:
        _table(libs, "External Library (.jar)")

    st.divider()
    st.markdown("##### Detailed Architecture Diagram — Components, Subjobs, Trigger Links, Execution Order")
    _render_detailed_diagram(job)


_TRIGGER_RE = re.compile(r"SUBJOB|RUN_IF|COMPONENT_OK|COMPONENT_ERROR|ITERATE|^OK$|^ERROR$", re.I)


def _build_subjobs(components: list, connections: list):
    """Group components into subjobs via data-flow links (Union-Find) and
    separate out trigger/control links. Built only from already-parsed
    job_data['components'] / job_data['connections'] — no XML re-parsing."""
    names = [c.get("unique_name") or c.get("component_type") for c in components]
    parent = {n: n for n in names}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    data_edges, trigger_edges = [], []
    for conn in connections:
        s, t, ctype = conn.get("source"), conn.get("target"), conn.get("connector") or ""
        if s not in parent or t not in parent:
            continue
        if _TRIGGER_RE.search(ctype):
            trigger_edges.append((s, t, ctype))
        else:
            data_edges.append((s, t, ctype))
            union(s, t)

    groups = {}
    for n in names:
        groups.setdefault(find(n), []).append(n)
    subjob_list = list(groups.values())
    comp_to_subjob = {m: i for i, members in enumerate(subjob_list) for m in members}
    return subjob_list, data_edges, trigger_edges, comp_to_subjob


def _execution_order(subjob_list, trigger_edges, comp_to_subjob):
    """Topological order of subjobs derived purely from trigger-link metadata."""
    n = len(subjob_list)
    adj = {i: set() for i in range(n)}
    for s, t, _ in trigger_edges:
        si, ti = comp_to_subjob.get(s), comp_to_subjob.get(t)
        if si is not None and ti is not None and si != ti:
            adj[si].add(ti)
    indeg = {i: 0 for i in range(n)}
    for i in adj:
        for j in adj[i]:
            indeg[j] += 1
    order, queue, visited = [], [i for i in range(n) if indeg[i] == 0], set()
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        order.append(node)
        for j in adj[node]:
            indeg[j] -= 1
            if indeg[j] == 0:
                queue.append(j)
    order += [i for i in range(n) if i not in visited]
    return order


def _render_detailed_diagram(job: dict):
    jd = job["job_data"]
    components, connections = jd.get("components", []), jd.get("connections", [])
    if not components:
        st.caption("No component-level metadata available for this job.")
        return

    subjob_list, data_edges, trigger_edges, comp_to_subjob = _build_subjobs(components, connections)
    order = _execution_order(subjob_list, trigger_edges, comp_to_subjob)
    type_lookup = {(c.get("unique_name") or c.get("component_type")): c.get("component_type", "")
                   for c in components}

    dot = ['digraph G {', 'rankdir=TB; fontname="Arial";',
           'node[shape=box,style=filled,fontsize=10,fontname="Arial",'
           'fillcolor="#6366f1",fontcolor="white",color="none"];']
    for idx, members in enumerate(subjob_list):
        dot.append(f'subgraph cluster_{idx} {{ label="Subjob {idx + 1}"; '
                   f'style=rounded; color="#94a3b8"; fontsize=11; fontname="Arial";')
        for m in members:
            label = f"{m}\\n({type_lookup.get(m, '')})"
            dot.append(f'"{m}" [label="{label}"];')
        dot.append("}")
    for s, t, ctype in data_edges:
        dot.append(f'"{s}" -> "{t}" [color="#0ea5e9",label="{ctype}",fontsize=8,fontcolor="#0ea5e9"];')
    for s, t, ctype in trigger_edges:
        dot.append(f'"{s}" -> "{t}" [color="#dc2626",style=dashed,label="{ctype}",fontsize=8,fontcolor="#dc2626"];')
    dot.append("}")
    st.graphviz_chart("\n".join(dot))

    st.markdown("**Execution Order** (subjob sequence derived from trigger links):")
    st.markdown(" → ".join(f"Subjob {i + 1}" for i in order) or "—")

    with st.expander("Trigger Links"):
        if trigger_edges:
            st.dataframe(pd.DataFrame(trigger_edges, columns=["Source", "Target", "Trigger Type"]),
                         use_container_width=True, hide_index=True)
        else:
            st.caption("No trigger links (SUBJOB_OK / RUN_IF / OnComponentOk / etc.) detected for this job.")


# ── Source Architecture ────────────────────────────────────────────────────────

def _render_source_architecture():
    all_jobs = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        st.info("⬜ No repository loaded. Upload and analyse a Talend repository to populate this section.")
        return

    job_names = sorted({j["job_data"].get("job_name", "—") for j in all_jobs})
    selected = st.selectbox("Select Job", job_names, key=f"tdd_src_job_sel{_KEY_CTX}")
    job = next((j for j in all_jobs if j["job_data"].get("job_name") == selected), all_jobs[0])
    jd = job["job_data"]
    components = jd.get("components", [])
    inv = build_source_target_inventory(jd)          # existing parser output — reused as-is
    sources, source_systems = inv["sources"], inv["source_systems"]
    src_unique_names = {s["unique_name"] for s in sources}
    api_components = [c for c in components
                       if _API_TYPE_RE.search(c.get("component_type", ""))
                       and c.get("unique_name") not in src_unique_names]

    def _df(rows, col):
        if rows:
            st.dataframe(pd.DataFrame({col: rows}), use_container_width=True, hide_index=True)
        else:
            st.caption(f"No {col.lower()} identified for this job.")

    tabs = st.tabs(["Source Systems", "Source Components", "Source Tables",
                    "Source Files", "Source APIs", "Connection Types", "Input Schemas"])

    with tabs[0]:
        if source_systems:
            st.dataframe(pd.DataFrame(source_systems).rename(
                columns={"system": "Source System", "count": "Components"}),
                use_container_width=True, hide_index=True)
        else:
            st.caption("No source systems identified for this job.")

    with tabs[1]:
        _df(sorted({s["component"] for s in sources}), "Source Component")

    with tabs[2]:
        _df(sorted({s["qualified_name"] for s in sources if s["physical_ref"].table}), "Source Table")

    with tabs[3]:
        _df(sorted({s["physical_ref"].file_name or s["name"] for s in sources
                    if s["physical_ref"].is_file}), "Source File")

    with tabs[4]:
        _df(sorted({c.get("component_type", "") for c in api_components}), "Source API Component")

    with tabs[5]:
        conn_types = sorted({s["type"] for s in sources if s["type"]})
        if api_components:
            conn_types.append("REST/API")
        _df(sorted(set(conn_types)), "Connection Type")

    with tabs[6]:
        rows = [{"Component": s["unique_name"], "Schema/Owner": s["physical_ref"].schema}
                for s in sources if s["physical_ref"].schema]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No input schema/owner metadata resolved for this job's sources.")


# ── Target Architecture ────────────────────────────────────────────────────────

def _render_target_architecture():
    all_jobs = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        st.info("⬜ No repository loaded. Upload and analyse a Talend repository to populate this section.")
        return

    job_names = sorted({j["job_data"].get("job_name", "—") for j in all_jobs})
    selected = st.selectbox("Select Job", job_names, key=f"tdd_tgt_job_sel{_KEY_CTX}")
    job = next((j for j in all_jobs if j["job_data"].get("job_name") == selected), all_jobs[0])
    jd = job["job_data"]
    inv = build_source_target_inventory(jd)          # existing parser output — reused as-is
    targets, target_systems = inv["targets"], inv["target_systems"]

    def _df(rows, col):
        if rows:
            st.dataframe(pd.DataFrame({col: rows}), use_container_width=True, hide_index=True)
        else:
            st.caption(f"No {col.lower()} identified for this job.")

    tabs = st.tabs(["Target Systems", "Target Components", "Target Tables",
                    "Target Files", "Output Schemas", "Data Models"])

    with tabs[0]:
        if target_systems:
            st.dataframe(pd.DataFrame(target_systems).rename(
                columns={"system": "Target System", "count": "Components"}),
                use_container_width=True, hide_index=True)
        else:
            st.caption("No target systems identified for this job.")

    with tabs[1]:
        _df(sorted({t["component"] for t in targets}), "Target Component")

    with tabs[2]:
        _df(sorted({t["qualified_name"] for t in targets if t["physical_ref"].table}), "Target Table")

    with tabs[3]:
        _df(sorted({t["physical_ref"].file_name or t["name"] for t in targets
                    if t["physical_ref"].is_file}), "Target File")

    with tabs[4]:
        rows = [{"Component": t["unique_name"], "Schema/Owner": t["physical_ref"].schema}
                for t in targets if t["physical_ref"].schema]
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No output schema/owner metadata resolved for this job's targets.")

    with tabs[5]:
        models = {}
        for t in targets:
            ref = t["physical_ref"]
            if not ref.table:
                continue
            model_key = ".".join(p for p in (ref.db_type, ref.database or ref.schema) if p) or ref.db_type or "Unmodeled"
            models.setdefault(model_key, set()).add(ref.table.upper())
        if models:
            st.dataframe(pd.DataFrame(
                [{"Data Model": k, "Tables": ", ".join(sorted(v)), "Table Count": len(v)}
                 for k, v in models.items()]), use_container_width=True, hide_index=True)
        else:
            st.caption("No data model groupings resolved for this job's targets.")


# ── Source-To-Target Mapping ────────────────────────────────────────────────────

def _render_mapping():
    all_jobs = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        st.info("⬜ No repository loaded. Upload and analyse a Talend repository to populate this section.")
        return

    job_names = sorted({j["job_data"].get("job_name", "—") for j in all_jobs})
    selected = st.selectbox("Select Job", job_names, key=f"tdd_map_job_sel{_KEY_CTX}")
    job = next((j for j in all_jobs if j["job_data"].get("job_name") == selected), all_jobs[0])
    mappings = job["job_data"].get("column_mappings", [])

    if not mappings:
        st.caption("No tMap column-level mappings found for this job (re-run analysis to populate, "
                   "or this job has no tMap components).")
        return

    rows = [{
        "Source Column": f'{m["Source Component"]}.{m["Source Column"]}',
        "Transformation": f'{m["Expression"]} [{m["Migration Rule"]}]',
        "Target Column": f'{m["Target Component"]}.{m["Target Column"]}',
        "Data Type Conversion": m["Data Type Conversion"],
        "Default Value": m["Default Value"],
    } for m in mappings]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    rules = job["job_data"].get("mapping_rules", [])
    lookups = [r for r in rules if r["Rule Type"] == "Lookup"]
    filters = [r for r in rules if r["Rule Type"] == "Filter"]

    tabs = st.tabs(["Lookup Mappings", "Join Conditions", "Filters", "Lookup Sources"])
    with tabs[0]:
        if lookups:
            st.dataframe(pd.DataFrame([{"tMap": l["tMap"], "Lookup Table": l["Table"],
                                        "Lookup Source": l["Lookup Source"], "Match Mode": l["Match Mode"]}
                                       for l in lookups]), use_container_width=True, hide_index=True)
        else:
            st.caption("No lookup inputs detected on this job's tMap components.")
    with tabs[1]:
        if lookups:
            st.dataframe(pd.DataFrame([{"tMap": l["tMap"], "Lookup Table": l["Table"], "Join Type": l["Join Type"]}
                                       for l in lookups]), use_container_width=True, hide_index=True)
        else:
            st.caption("No join conditions detected on this job's tMap components.")
    with tabs[2]:
        if filters:
            st.dataframe(pd.DataFrame([{"tMap": f["tMap"], "Table": f["Table"], "Filter Expression": f["Filter Expression"]}
                                       for f in filters]), use_container_width=True, hide_index=True)
        else:
            st.caption("No filter conditions detected on this job's tMap components.")
    with tabs[3]:
        sources = sorted({l["Lookup Source"] for l in lookups})
        if sources:
            st.dataframe(pd.DataFrame({"Lookup Source Component": sources}), use_container_width=True, hide_index=True)
        else:
            st.caption("No lookup source components identified for this job.")


# ── shared job selector ───────────────────────────────────────────────────────

def _select_job(key: str):
    all_jobs = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        st.info("⬜ No repository loaded. Upload and analyse a Talend repository to populate this section.")
        return None
    job_names = sorted({j["job_data"].get("job_name", "—") for j in all_jobs})
    selected = st.selectbox("Select Job", job_names, key=key)
    job = next((j for j in all_jobs if j["job_data"].get("job_name") == selected), all_jobs[0])
    return job["job_data"]


def _render_findings_card(findings: list[str], empty_msg: str = "No findings."):
    if not findings:
        st.caption(empty_msg)
        return
    for f in findings:
        st.markdown(f"- {f}")


# ── Quality Sections (Phase 17D) ──────────────────────────────────────────────

def _render_transformation_architecture():
    job_data = _select_job("tdd_transform_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_transformation_section(job_data)
    _render_findings_card(result["findings"])

    mappings = job_data.get("column_mappings", [])
    if mappings:
        rows = [{
            "tMap Expression": str(m.get("Expression", ""))[:100],
            "Target Column": f'{m.get("Target Component","")}.{m.get("Target Column","")}',
            "Data Type": m.get("Data Type Conversion", ""),
        } for m in mappings if m.get("Expression") and m.get("Expression") not in ("", "—")]
        if rows:
            st.markdown("**tMap Logic (sample)**")
            st.dataframe(pd.DataFrame(rows[:50]), use_container_width=True, hide_index=True)


def _render_job_flow_architecture():
    job_data = _select_job("tdd_jobflow_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_job_flow_section(job_data)
    _render_findings_card(result["findings"])

    all_jobs = st.session_state.get("last_analysis_jobs", [])
    if not all_jobs:
        return
    selected_name = job_data.get("job_name", "")
    job_wrap = next((j for j in all_jobs if j["job_data"].get("job_name") == selected_name), None)
    if job_wrap:
        _render_detailed_diagram(job_wrap)


def _render_column_lineage_tdd():
    job_data = _select_job("tdd_lineage_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_column_lineage_section(job_data)
    _render_findings_card(result["findings"])

    rows = result.get("lineage_rows", [])
    if rows:
        query = st.text_input("🔍 Search lineage", key=f"tdd_lineage_search{_KEY_CTX}", placeholder="Filter by column or expression…")
        filtered = [r for r in rows if not query or query.lower() in str(r).lower()]
        st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(filtered)} of {len(rows)} lineage rows.")


def _render_validation():
    job_data = _select_job("tdd_validation_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_validation_section(job_data)
    _render_findings_card(result["findings"])


def _render_error_handling():
    job_data = _select_job("tdd_error_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_error_handling_section(job_data)
    _render_findings_card(result["findings"])


def _render_audit_monitoring():
    job_data = _select_job("tdd_audit_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_audit_monitoring_section(job_data)
    _render_findings_card(result["findings"])


# ── Advanced Sections (Phase 17E) ─────────────────────────────────────────────

def _render_performance():
    job_data = _select_job("tdd_perf_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_performance_section(job_data)
    _render_findings_card(result["findings"])


def _render_security():
    job_data = _select_job("tdd_security_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_security_section(job_data)
    _render_findings_card(result["findings"])


def _render_dependency_architecture():
    job_data = _select_job("tdd_dep_job_sel")
    if job_data is None:
        return
    result = tdd_sections.generate_dependency_section(job_data)
    _render_findings_card(result["findings"])


def _render_testing_section():
    job_data = _select_job("tdd_testing_job_sel")
    if job_data is None:
        return
    arch = build_testing_architecture(job_data)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unit Tests", len(arch["unit_tests"]))
    c2.metric("Validation SQL", len(arch["validation_sql"]))
    c3.metric("Reconciliation Rules", len(arch["reconciliation_rules"]))
    c4.metric("Src vs Target Checks", len(arch["src_vs_tgt"]))

    st.divider()

    if arch["unit_tests"]:
        st.markdown("**Top Unit Tests**")
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        top = sorted(arch["unit_tests"], key=lambda t: priority_order.get(t.get("priority", "LOW"), 3))[:5]
        st.dataframe(pd.DataFrame([{
            "ID": t["tc_id"],
            "Component": t["component"],
            "Priority": t["priority"],
            "Objective": t["objective"],
        } for t in top]), use_container_width=True, hide_index=True)

    st.caption("Full expandable detail available on the 🧪 Testing tab.")


# ── Final Sections (Phase 17F) ────────────────────────────────────────────────

def _render_migration_assessment_section():
    job_data = _select_job("tdd_ma_job_sel")
    if job_data is None:
        return
    assess = build_migration_assessment(job_data)
    c1, c2 = st.columns(2)
    c1.metric("Cloud Readiness", assess["cloud_readiness"]["readiness"])
    c2.metric("Estimated Hours", assess["effort_estimation"]["estimated_hours"])
    st.markdown("**Top Recommendations:**")
    _render_findings_card(assess["recommendations"][:5])
    st.caption("Full detail available on the Migration Assessment page.")


def _render_ai_summary_section():
    job_data = _select_job("tdd_ai_summary_job_sel")
    if job_data is None:
        return
    summary = build_executive_summary(job_data)
    st.markdown("**Business Summary**")
    st.markdown(summary["business_summary"])
    st.markdown("**Technical Summary**")
    st.markdown(summary["technical_summary"])
    st.caption("Full detail available on the AI Executive Summary page.")


# ── section registry ──────────────────────────────────────────────────────────

_SECTIONS = [
    ("📋", "Executive Summary",             None),
    ("🏛️", "Job Architecture",             "High-level and detailed job architecture: parent/child jobs, joblets, context groups, routines, and external libraries."),
    ("🔵", "Source Architecture",           "Source systems, components, tables, files, APIs, connection types, and input schemas — from existing parser output."),
    ("🟢", "Target Architecture",           "Target systems, components, tables, files, output schemas, and data models — from existing parser output."),
    ("🔗", "Source-To-Target Mapping",      "Column-level mapping: source column, transformation, target column, data type conversion, default values — from existing tMap parser output."),
    ("⚙️", "Transformation Architecture",  "tMap logic, tJava/tJavaRow, aggregations, surrogate keys, context variables, data conversions, filters."),
    ("🔀", "Job Flow Architecture",         "End-to-end flow, component sequence, trigger links, subjobs, and execution order."),
    ("🔍", "Column Lineage",               "Source column → transformation → target column lineage, searchable lineage table."),
    ("✅", "Validation",                   "Data validation rules, reconciliation checks, and acceptance criteria."),
    ("🚨", "Error Handling",               "Exception flows, dead-letter queues, retry strategies, and alerting."),
    ("📝", "Audit",                        "Audit trail design, logging standards, lineage tracking, and compliance metadata."),
    ("⚡", "Performance",                  "Throughput targets, parallelism settings, memory configuration, and SLAs."),
    ("🔒", "Security",                     "Data masking, PII handling, encryption, access control, and compliance requirements."),
    ("🕸️", "Dependencies",                 "Job orchestration order, upstream/downstream dependencies, and third-party systems."),
    ("🧪", "Testing",                      "Unit, integration, regression, and UAT strategy, test cases, and sign-off criteria."),
    ("📊", "Migration Assessment",         "Risk register, effort estimates, readiness scores, and go-live recommendations."),
    ("🤖", "AI Summary",                   "AI-generated insights, anomaly flags, and intelligent migration recommendations."),
]


# ── Download TDD (Phase 18) ───────────────────────────────────────────────────

def _render_tdd_download_section(_key_suffix: str = ""):
    from app.tiap.documentation.tdd_export import (
        build_tdd_markdown, build_tdd_html, markdown_to_html, write_docx, _write_tdd_pdf,
        _inject_diagrams_docx, _build_pipeline_dot, _build_flow_dot, _build_dependency_dot,
    )
    from app.tiap.documentation import tdd_sections as _tdd_sec
    from app.tiap.testing.testing_architecture import build_testing_architecture
    from app.tiap.migration_assessment.migration_assessment import build_migration_assessment
    from app.tiap.exec_summary.exec_summary import build_executive_summary
    from app.parser.source_target_extractor import build_source_target_inventory

    # ── Section map: label → markdown heading keyword ─────────────────────────
    _SECTION_HEADINGS = [
        ("📋 Executive Summary",          "## Executive Summary"),
        ("🏛️ Job Architecture",           "## Job Architecture"),
        ("🔵 Source Architecture",         "## Source Architecture"),
        ("🟢 Target Architecture",         "## Target Architecture"),
        ("🔗 Source-To-Target Mapping",    "## Source-To-Target Mapping"),
        ("⚙️ Transformation Architecture", "## Transformation Architecture"),
        ("🔀 Job Flow Architecture",       "## Job Flow Architecture"),
        ("🔍 Column Lineage",              "## Column Lineage"),
        ("✅ Validation",                  "## Validation"),
        ("🚨 Error Handling",              "## Error Handling"),
        ("📝 Audit",                       "## Audit & Monitoring"),
        ("⚡ Performance",                 "## Performance"),
        ("🔒 Security",                    "## Security"),
        ("🕸️ Dependencies",               "## Dependency Architecture"),
        ("🧪 Testing",                     "## Testing"),
        ("📊 Migration Assessment",        "## Migration Assessment"),
        ("🤖 AI Summary",                  "## AI Executive Summary"),
    ]

    job_data = _select_job(f"tdd_download_job_sel{_key_suffix}")
    if job_data is None:
        return

    job_name = job_data.get("job_name", "Unknown")

    # ── Section selector ──────────────────────────────────────────────────────
    st.markdown("**Select Sections to Export**")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ All", key=f"tdd_sel_all{_key_suffix}", use_container_width=True):
            for label, _ in _SECTION_HEADINGS:
                st.session_state[f"tdd_sec_{label}{_key_suffix}"] = True
    with col_b:
        if st.button("☐ None", key=f"tdd_sel_none{_key_suffix}", use_container_width=True):
            for label, _ in _SECTION_HEADINGS:
                st.session_state[f"tdd_sec_{label}{_key_suffix}"] = False

    selected_headings = []
    for label, heading in _SECTION_HEADINGS:
        checked = st.checkbox(label, value=st.session_state.get(f"tdd_sec_{label}{_key_suffix}", True),
                              key=f"tdd_sec_chk_{label}{_key_suffix}")
        st.session_state[f"tdd_sec_{label}{_key_suffix}"] = checked
        if checked:
            selected_headings.append(heading)

    # ── Format selector ───────────────────────────────────────────────────────
    st.markdown("**Export Format**")
    fmt_options = ["📝 Markdown (.md)", "🌐 HTML (.html)", "📄 Word (.docx)", "📕 PDF (.pdf)"]
    fmt_keys    = ["markdown", "html", "docx", "pdf"]
    selected_fmts = st.multiselect("Formats", fmt_options, default=fmt_options,
                                   key=f"tdd_dl_fmt_sel{_key_suffix}", label_visibility="collapsed")

    # ── Generate ──────────────────────────────────────────────────────────────
    if st.button("Generate Exports", key=f"tdd_generate_exports_btn{_key_suffix}", use_container_width=True):
        if not selected_headings:
            st.warning("Select at least one section.")
        else:
            with st.spinner("Building selected sections…"):
                try:
                    full_md = build_tdd_markdown(job_data)
                    # Split full markdown by H2 headings, keep only selected
                    import re as _re
                    parts = _re.split(r'(?=\n## )', "\n" + full_md)
                    title_line = parts[0].strip()  # # TDD title
                    filtered = [title_line, ""]
                    for part in parts[1:]:
                        for h in selected_headings:
                            if part.strip().startswith(h):
                                filtered.append(part.strip())
                                filtered.append("")
                                break
                    filtered_md = "\n".join(filtered)

                    out_dir = os.path.join("/tmp", "tma_tdd_exports", _safe_job_name(job_name))
                    os.makedirs(out_dir, exist_ok=True)
                    title = f"{job_name} — Technical Design Document"
                    sel_keys = [fmt_keys[fmt_options.index(f)] for f in selected_fmts]

                    paths = {}
                    if "markdown" in sel_keys:
                        p = os.path.join(out_dir, f"{_safe_job_name(job_name)}_TDD.md")
                        with open(p, "w", encoding="utf-8") as f:
                            f.write(filtered_md)
                        paths["markdown"] = p
                    if "html" in sel_keys:
                        # Use the rich HTML builder (diagrams, KPI grids, RAG badges),
                        # filtered to the selected sections — NOT markdown_to_html(filtered_md),
                        # which only knows plain text and drops all styling/diagrams.
                        p = os.path.join(out_dir, f"{_safe_job_name(job_name)}_TDD.html")
                        with open(p, "w", encoding="utf-8") as f:
                            f.write(build_tdd_html(job_data, selected_headings=selected_headings))
                        paths["html"] = p
                    if "docx" in sel_keys:
                        from app.tiap.documentation.export_utils import write_docx as _wdocx
                        p = os.path.join(out_dir, f"{_safe_job_name(job_name)}_TDD.docx")
                        _wdocx(p, title, filtered_md)
                        try:
                            # Same diagram injection export_tdd() uses for the full
                            # document — naturally filter-safe since it only inserts
                            # a diagram after a heading paragraph that actually exists.
                            _inject_diagrams_docx(p, job_data)
                        except Exception:
                            pass
                        paths["docx"] = p
                    if "pdf" in sel_keys:
                        p = os.path.join(out_dir, f"{_safe_job_name(job_name)}_TDD.pdf")
                        diagram_pngs = {}
                        diagram_markers = [
                            ("## Job Architecture",        "pipeline", _build_pipeline_dot),
                            ("## Job Flow Architecture",   "flow",     _build_flow_dot),
                            ("## Dependency Architecture", "dep",      _build_dependency_dot),
                        ]
                        md_with_markers = filtered_md
                        for heading, key, dot_fn in diagram_markers:
                            if heading not in selected_headings:
                                continue
                            try:
                                import graphviz as _graphviz
                                png = _graphviz.Source(dot_fn(job_data)).pipe(format="png")
                                if png:
                                    diagram_pngs[key] = png
                                    md_with_markers = md_with_markers.replace(
                                        f"{heading}\n", f"{heading}\n[DIAGRAM:{key}]\n")
                            except Exception:
                                pass
                        _write_tdd_pdf(p, md_with_markers, title, diagram_pngs)
                        paths["pdf"] = p

                    st.session_state[f"tdd_export_paths{_key_suffix}"] = paths
                    st.success(f"Exported {len(selected_headings)} section(s) in {len(paths)} format(s).")
                except Exception as e:
                    st.error(f"Export failed: {e}")

    paths = st.session_state.get(f"tdd_export_paths{_key_suffix}")
    if paths:
        fmt_labels = {"markdown": "📝 Markdown (.md)", "html": "🌐 HTML (.html)",
                      "docx": "📄 Word (.docx)", "pdf": "📕 PDF (.pdf)"}
        for fmt, path in paths.items():
            if os.path.exists(path):
                with open(path, "rb") as f:
                    st.download_button(
                        fmt_labels.get(fmt, fmt), data=f.read(),
                        file_name=os.path.basename(path), key=f"tdd_dl_{fmt}{_key_suffix}",
                        use_container_width=True,
                    )


# ── page entry point ──────────────────────────────────────────────────────────

def render_tdd_page():
    page_header("📄", "Technical Design Document",
                "Structured TDD for Talend migration — all sections editable per engagement.")

    col_l, col_r = st.columns([6, 2])
    with col_l:
        st.caption("Executive Summary and all analysis sections are auto-populated per selected job.")
    with col_r:
        _tdd_export_popover = st.popover("⬇️  Download TDD", use_container_width=True)
        with _tdd_export_popover:
            _render_tdd_download_section()

    st.divider()

    section_labels = [f"{icon} {name}" for icon, name, _ in _SECTIONS]
    selected_label = st.radio(
        "Jump to section", section_labels,
        horizontal=True, label_visibility="collapsed", key=f"tdd_section_nav{_KEY_CTX}",
    )
    selected_idx = section_labels.index(selected_label)

    st.divider()

    icon, name, desc = _SECTIONS[selected_idx]
    label_html = (
        f'<div style="border-left:4px solid #6366f1;padding:6px 0 4px 14px;margin-bottom:10px;">' +
        f'<span style="font-size:20px">{icon}</span> ' +
        f'<span style="font-size:17px;font-weight:700;color:#0f172a">{name}</span>' +
        (f'<br><span style="font-size:12px;color:#64748b">{desc}</span>' if desc else '') +
        '</div>'
    )
    st.markdown(label_html, unsafe_allow_html=True)

    _RENDERERS = [
        _render_executive_summary,
        _render_architecture,
        _render_source_architecture,
        _render_target_architecture,
        _render_mapping,
        _render_transformation_architecture,
        _render_job_flow_architecture,
        _render_column_lineage_tdd,
        _render_validation,
        _render_error_handling,
        _render_audit_monitoring,
        _render_performance,
        _render_security,
        _render_dependency_architecture,
        _render_testing_section,
        _render_migration_assessment_section,
        _render_ai_summary_section,
    ]
    _RENDERERS[selected_idx]()
