from app.ai.context_accessor import get_ai_context
from app.parser.source_target_extractor import build_source_target_inventory
from app.tiap.graph.flowchart_generator import FlowchartGenerator


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _technical_flowchart_prompt(job_data: dict) -> str:
    components = [c["component_type"] for c in job_data.get("components", [])]
    inv = build_source_target_inventory(job_data)
    return (
        f"Create a simple technical flowchart for Talend job: {job_data['job_name']}.\n"
        f"Source Tables/Files: {', '.join(inv['source_names'])}\n"
        f"Target Tables/Files: {', '.join(inv['target_names'])}\n"
        f"Components in order: {' → '.join(components[:15])}\n\n"
        "Show the component pipeline as a vertical flowchart using arrows (→).\n"
        "Format:\n"
        "[Component1]\n   ↓\n[Component2]\n   ↓\n...\n\n"
        "Only include the diagram. No explanation needed."
    )


def _business_flowchart_prompt(job_data: dict) -> str:
    inv = build_source_target_inventory(job_data)
    src = inv["source_names"][0] if inv["source_names"] else "Source"
    tgt = inv["target_names"][0] if inv["target_names"] else "Target"
    return (
        f"Create a simple business flowchart for Talend job: {job_data['job_name']}.\n"
        f"Source: {src}, Target: {tgt}\n\n"
        "Show the business data flow in plain English using arrows.\n"
        "Example:\n"
        "[Source Data]\n   ↓\n[Validation]\n   ↓\n[Business Rules]\n   ↓\n[Target Table]\n\n"
        "Only include the diagram. Keep labels short and business-friendly."
    )


# ---------------------------------------------------------------------------
# Rule-based flowchart generators
# ---------------------------------------------------------------------------

def _make_box(text: str, width: int = 30) -> str:
    text = text[:width - 2]
    pad  = width - len(text) - 2
    return f"[ {text}{' ' * pad}]"


def generate_technical_flowchart(job_data: dict, use_ai: bool = False) -> str:
    """Business-readable migration-ready technical flowchart."""
    ctx = get_ai_context() if use_ai else {}
    ai_note = ctx.get("technical_flowchart_notes", "")

    flow = FlowchartGenerator().technical_flow([{"job_data": job_data}], job_data.get("job_name"))
    if flow and flow != "No technical flow detected":
        return flow + (f"\n\n// AI Notes: {ai_note}" if ai_note else "")

    comps   = job_data.get("components", [])
    inv     = build_source_target_inventory(job_data)
    sources = inv["source_names"]
    targets = inv["target_names"]
    sql_ops = inv["sql_operations"]

    # Transformation mapping
    mapping = {
        "tMap":          "Data Mapping",
        "tAggregateRow": "Aggregate Records",
        "tJoin":         "Join Datasets",
        "tFilterRow":    "Filter Records",
        "tUnpivotRow":   "Unpivot Data",
        "tSortRow":      "Sort Records",
        "tJavaRow":      "Custom Business Logic",
        "tJava":         "Custom Java Processing",
        "tJavaFlex":     "Flexible Java Processing",
        "tNormalize":    "Normalize Data",
        "tDenormalize":  "Denormalize Data",
        "tReplicate":    "Duplicate Data Stream",
    }
    transforms = []
    childs     = []
    audits     = []

    for c in comps:
        ct = c.get("component_type", "")
        if ct in mapping:
            transforms.append(mapping[ct])
        if ct == "tRunJob":
            params  = c.get("parameters", {})
            target  = (
                params.get("PROCESS", "")
                or c.get("job_name", "")
                or c.get("target_job", "")
                or c.get("unique_name", "Child Job")
            )
            childs.append(target.strip('"').strip("'") or "Child Job")
        if "Log" in ct or "Stat" in ct or "Catcher" in ct:
            audits.append(ct)

    src_label = ", ".join(sources) if sources and sources != ["(none detected)"] else "Repository / Control Table"
    tgt_label = ", ".join(targets) if targets and targets != ["(none detected)"] else "Status / Target Tables"

    lines = [
        f"Technical Flowchart: {job_data['job_name']}",
        "=" * 60,
        "[ START ]",
        "   ↓",
        f"[ Source: {src_label} ]",
        "   ↓",
    ]

    if transforms:
        lines.append("[ Transformations ]")
        for t in dict.fromkeys(transforms):
            lines.append(f"  • {t}")
        lines.append("   ↓")

    if sql_ops:
        lines.append("[ SQL Execution Operations ]")
        for op in sql_ops[:5]:
            q = op.get("query", "")[:60] or op["component"]
            lines.append(f"  • {op['component']}: {q}")
        lines.append("   ↓")

    lines += ["[ Trigger Conditions ]", "  • RunIf / OnSubjobOK / Validation", "   ↓"]

    for ch in childs:
        lines += [f"[ Execute Child Job: {ch} ]", "   ↓"]

    lines += [
        f"[ Target: {tgt_label} ]",
        "   ↓",
        f"[ Audit / Logging{': ' + ', '.join(audits[:3]) if audits else '' } ]",
        "   ↓",
        "[ Error Handling Path ]",
        "   ↓",
        "[ END ]",
    ]
    return "\n".join(lines)


def generate_business_flowchart(job_data: dict, use_ai: bool = False) -> str:
    """Returns a business-language flowchart."""
    ctx = get_ai_context() if use_ai else {}
    ai_note = ctx.get("business_flowchart_notes", "")

    flow = FlowchartGenerator().business_flow([{"job_data": job_data}], job_data.get("job_name"))
    if flow and flow != "No business flow detected":
        return flow + (f"\n\n// AI Notes: {ai_note}" if ai_note else "")

    components = [c["component_type"] for c in job_data.get("components", [])]
    inv = build_source_target_inventory(job_data)

    steps = []
    seen  = set()

    def add_step(label):
        if label not in seen:
            seen.add(label)
            steps.append(label)

    # First: source step with actual name
    src_name = inv["source_names"][0] if inv["source_names"] != ["(none detected)"] else None
    if src_name:
        add_step(f"Read Source: {src_name}")
    else:
        for comp in components:
            if "Input" in comp:
                add_step("Source Data Read")
                break

    for comp in components:
        if "Filter" in comp:
            add_step("Data Filtering / Validation")
        elif "Map" in comp:
            add_step("Data Transformation (Business Rules)")
        elif "Log" in comp or "Warn" in comp:
            add_step("Logging / Alerting")
        elif "RunJob" in comp:
            add_step("Child Job Execution")
        elif "Context" in comp:
            add_step("Context / Configuration Load")

    # Last: target step with actual name
    tgt_name = inv["target_names"][0] if inv["target_names"] != ["(none detected)"] else None
    if tgt_name:
        add_step(f"Load Target: {tgt_name}")
    else:
        for comp in components:
            if "Output" in comp:
                add_step("Target Data Load")
                break

    if not steps:
        steps = ["Data Extraction", "Data Processing", "Data Load"]

    lines = [
        f"Business Flowchart: {job_data['job_name']}",
        "=" * 40,
    ]
    for i, step in enumerate(steps):
        lines.append(_make_box(step, 40))
        if i < len(steps) - 1:
            lines.append("         ↓")
    return "\n".join(lines)


def generate_parent_child_flowchart(job_data: dict, all_jobs: list = None) -> str:
    """Returns upstream and downstream job dependency flowchart."""
    if all_jobs:
        flow = FlowchartGenerator().parent_child_flow(all_jobs)
        if flow and flow != "No parent child dependencies":
            return flow

    jname = job_data["job_name"]
    child_refs = []

    if all_jobs:
        for job in all_jobs:
            jd    = job.get("job_data", {})
            comps = jd.get("components", [])
            for comp in comps:
                if comp.get("component_type") == "tRunJob":
                    params = comp.get("parameters", {})
                    target = (
                        params.get("PROCESS", "")
                        or comp.get("job_name", "")
                        or comp.get("target_job", "")
                        or comp.get("child_job", "")
                        or comp.get("unique_name", "")
                    )
                    target = target.strip('"').strip("'")
                    if jd.get("job_name") == jname and target:
                        child_refs.append(target)

    parents = []
    if all_jobs:
        for job in all_jobs:
            jd = job.get("job_data", {})
            if jd.get("job_name") == jname:
                continue
            for comp in jd.get("components", []):
                if comp.get("component_type") == "tRunJob":
                    params = comp.get("parameters", {})
                    target = (
                        params.get("PROCESS", "")
                        or comp.get("job_name", "")
                        or comp.get("target_job", "")
                        or comp.get("child_job", "")
                        or ""
                    ).strip('"').strip("'")
                    if target == jname:
                        parents.append(jd.get("job_name"))
                        break

    lines = [
        f"Parent-Child Flowchart: {jname}",
        "=" * 40,
    ]
    role = "MASTER JOB" if child_refs else "JOB"
    lines.append(_make_box(jname, 36) + f"  ← {role}")

    if parents:
        lines.append("")
        lines.append("UPSTREAM PARENTS:")
        for p in parents:
            lines.append(f"    └── {_make_box(p, 28)}")

    lines.append("    │")
    if child_refs:
        for i, child in enumerate(child_refs[:10]):
            connector = "    ├──" if i < len(child_refs) - 1 else "    └──"
            lines.append(f"{connector} {_make_box(child, 28)}")
    else:
        lines.append("    └── (No child jobs detected)")

    return "\n".join(lines)


def generate_repository_flowchart() -> str:
    """Returns the standard TMA repository analysis pipeline flowchart."""
    stages = [
        ("Repository Upload",        "Upload Talend repository ZIP"),
        ("Repository Discovery",     "Scan for jobs, routines, joblets"),
        ("Source / Target Mapping",  "Extract tables, files, queries per job"),
        ("Component Analysis",       "Custom + deprecated detection"),
        ("Dependency Analysis",      "Parent-child job mapping"),
        ("Java Risk Assessment",     "tJava / tJavaFlex risk scoring"),
        ("Cloud Readiness",          "Cloud blocker detection"),
        ("Migration Readiness",      "Readiness score calculation"),
        ("Documentation Generation", "Tech + Functional + KT docs"),
        ("Test Case Generation",     "7 test categories per job"),
        ("Remediation Planning",     "Auto-fix + manual action list"),
        ("Migration",                "Talend 8 / Cloud migration"),
        ("Validation",               "Post-migration validation"),
        ("Executive Dashboard",      "KPI reporting + effort estimate"),
    ]
    lines = ["TMA Repository Pipeline Flowchart", "=" * 50]
    for i, (stage, desc) in enumerate(stages):
        lines.append(f"[ {stage:<30}]  {desc}")
        if i < len(stages) - 1:
            lines.append("         ↓")
    return "\n".join(lines)


def generate_all_flowcharts(job_data: dict, all_jobs: list = None,
                             use_ai: bool = False) -> dict:
    """Returns all 4 flowchart types for a job."""
    return {
        "technical":    generate_technical_flowchart(job_data, use_ai=use_ai),
        "business":     generate_business_flowchart(job_data, use_ai=use_ai),
        "parent_child": generate_parent_child_flowchart(job_data, all_jobs),
        "repository":   generate_repository_flowchart(),
    }