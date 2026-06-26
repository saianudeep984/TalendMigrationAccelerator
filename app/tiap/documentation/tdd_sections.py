"""
TMA TDD Generator — Quality & Advanced Sections
Generates live, per-job analysis for: Validation, Error Handling, Audit & Monitoring,
Performance, Security, Dependency Architecture (Testing is covered by
app.tiap.testing.testing_architecture and Migration Assessment by
app.tiap.migration_assessment — both reused directly in tdd_page.py rather than
duplicated here).
"""
from __future__ import annotations
import re
from typing import Any

_TRIGGER_RE = re.compile(r"SUBJOB|RUN_IF|COMPONENT_OK|COMPONENT_ERROR|ITERATE|^OK$|^ERROR$", re.I)
_ERROR_HANDLERS = {"tDie", "tWarn", "tLogCatcher", "tAssertCatcher", "tStatCatcher", "tFlowMeterCatcher"}
_MONITORING_COMPONENTS = {"tStatCatcher", "tFlowMeter", "tFlowMeterCatcher", "tLogCatcher"}
_PARALLEL_COMPONENTS = {"tParallelize", "tPartitioner", "tDepartitionRecombiner"}
_DB_COMPONENT_PREFIXES = ("tMysql", "tOracle", "tPostgresql", "tMSSql", "tJDBC", "tSnowflake", "tBigQuery")


def _code_text(component: dict) -> str:
    params = component.get("parameters") or {}
    return " ".join(str(v) for v in params.values() if v)


# ── Validation ─────────────────────────────────────────────────────────────────

def generate_validation_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    types = [c.get("component_type", "") for c in components]

    validators = [t for t in types if t in {"tFilterRow", "tSchemaComplianceCheck", "tUniqRow"}]
    null_guards = sum(1 for c in components if "IF(" in _code_text(c) and ("=0" in _code_text(c) or "NULL" in _code_text(c).upper()))
    nullable_false = sum(
        1 for c in components
        for v in (c.get("parameters") or {}).values()
        if isinstance(v, str) and 'nullable="false"' in v
    )
    reject_links = [c for c in job_data.get("connections", []) if c.get("connector") == "REJECT"]

    findings = []
    if validators:
        findings.append(f"Explicit validation components present: {', '.join(sorted(set(validators)))}.")
    else:
        findings.append("No explicit validation components (tFilterRow / tSchemaComplianceCheck / tUniqRow) detected.")
    if null_guards:
        findings.append(f"{null_guards} SQL/expression-level null-safe guard pattern(s) detected.")
    if nullable_false:
        findings.append(f"{nullable_false} schema field(s) marked non-nullable.")
    if reject_links:
        findings.append(f"{len(reject_links)} REJECT connector link(s) present for row-level validation routing.")
    if not (validators or null_guards or nullable_false or reject_links):
        findings.append("Validation appears implicit only — no dedicated validation layer detected. Recommend adding explicit checks before migration.")

    return {"findings": findings, "validators": validators, "reject_link_count": len(reject_links)}


# ── Error Handling ─────────────────────────────────────────────────────────────

def generate_error_handling_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    types = {c.get("component_type", "") for c in components}
    handlers_found = sorted(types & _ERROR_HANDLERS)
    reject_links = [c for c in job_data.get("connections", []) if c.get("connector") == "REJECT"]
    error_links = [c for c in job_data.get("connections", []) if "ERROR" in str(c.get("connector", "")).upper()]
    die_on_error = sum(
        1 for c in components
        if str((c.get("parameters") or {}).get("DIE_ON_ERROR", "")).lower() == "true"
    )

    findings = []
    if handlers_found:
        findings.append(f"Error handling components present: {', '.join(handlers_found)}.")
    else:
        findings.append("No tDie / tWarn / tLogCatcher / tAssertCatcher components detected.")
    if error_links:
        findings.append(f"{len(error_links)} error-routing link(s) (OnComponentError / OnSubjobError) detected.")
    else:
        findings.append("No OnComponentError / OnSubjobError links detected.")
    if reject_links:
        findings.append(f"{len(reject_links)} REJECT link(s) present for row-level error capture.")
    if die_on_error:
        findings.append(f"{die_on_error} component(s) configured with DIE_ON_ERROR — hard abort, no capture.")

    return {"findings": findings, "handlers_found": handlers_found}


# ── Audit & Monitoring ─────────────────────────────────────────────────────────

def generate_audit_monitoring_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    types = {c.get("component_type", "") for c in components}
    monitoring_found = sorted(types & _MONITORING_COMPONENTS)
    audit_like_tables = [
        c for c in components
        for v in (c.get("parameters") or {}).values()
        if isinstance(v, str) and any(kw in v.lower() for kw in ("audit", "batch_id", "run_id", "execution_log"))
    ]
    log_row = sum(1 for t in types if t == "tLogRow")

    findings = []
    if monitoring_found:
        findings.append(f"Monitoring components present: {', '.join(monitoring_found)}.")
    else:
        findings.append("No tStatCatcher / tFlowMeter / tLogCatcher monitoring components detected.")
    if audit_like_tables:
        findings.append(f"{len(audit_like_tables)} reference(s) to audit/batch/run-id patterns detected in component parameters.")
    else:
        findings.append("No audit-table or batch/run-id tracking patterns detected.")
    if log_row:
        findings.append(f"{log_row} tLogRow component(s) present — console output only, not a persisted audit trail.")

    return {"findings": findings, "monitoring_found": monitoring_found}


# ── Performance ────────────────────────────────────────────────────────────────

def generate_performance_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    types = [c.get("component_type", "") for c in components]
    type_set = set(types)
    parallel_found = sorted(type_set & _PARALLEL_COMPONENTS)
    tmap_count = types.count("tMap")
    lookup_unparallelized = sum(
        1 for c in components
        if c.get("component_type") == "tMap"
        and str((c.get("parameters") or {}).get("LKUP_PARALLELIZE", "true")).lower() == "false"
    )
    run_job_count = types.count("tRunJob")

    findings = []
    if parallel_found:
        findings.append(f"Parallel execution components present: {', '.join(parallel_found)}.")
    else:
        findings.append("No tParallelize / tPartitioner components detected — execution likely sequential.")
    if tmap_count:
        findings.append(f"{tmap_count} tMap component(s) in job — review buffer/lookup memory settings for large datasets.")
    if lookup_unparallelized:
        findings.append(f"{lookup_unparallelized} tMap lookup(s) configured with LKUP_PARALLELIZE=false (single-threaded load).")
    if run_job_count > 1:
        findings.append(f"{run_job_count} tRunJob calls detected — verify whether chained subjobs could run in parallel.")
    if not findings:
        findings.append("No performance-relevant components detected.")

    return {"findings": findings, "parallel_found": parallel_found}


# ── Security ───────────────────────────────────────────────────────────────────

def generate_security_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    db_components = [c for c in components if str(c.get("component_type", "")).startswith(_DB_COMPONENT_PREFIXES)]
    plaintext_pass = []
    context_password = []
    ssl_found = False
    for c in db_components:
        params = c.get("parameters") or {}
        pass_val = str(params.get("PASS", ""))
        if pass_val and not pass_val.lower().startswith("context."):
            plaintext_pass.append(c.get("unique_name", c.get("component_type")))
        if "context." in str(params.get("PASS", "")).lower() or "context." in str(params.get("PASSWORD", "")).lower():
            context_password.append(c.get("unique_name", c.get("component_type")))
        if any("ssl" in str(k).lower() for k in params.keys()):
            ssl_found = True

    findings = []
    if db_components:
        findings.append(f"{len(db_components)} database connection component(s) detected.")
    if plaintext_pass:
        findings.append(f"{len(plaintext_pass)} component(s) with credentials not routed through a context variable — review for hardcoded passwords.")
    if context_password:
        findings.append(f"{len(context_password)} component(s) correctly reference context-based credentials.")
    if not ssl_found and db_components:
        findings.append("No SSL/TLS connection parameters detected on database components — verify encrypted transport before migration.")
    if not db_components:
        findings.append("No database connection components detected in this job.")

    return {"findings": findings, "plaintext_credentials": plaintext_pass}


# ── Dependency Architecture ────────────────────────────────────────────────────

def generate_dependency_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    run_job_calls = [c for c in components if c.get("component_type") == "tRunJob"]
    child_jobs = sorted({
        str((c.get("parameters") or {}).get("PROCESS_TYPE_PROCESS", "") or (c.get("parameters") or {}).get("PROCESS", ""))
        for c in run_job_calls
    } - {""})

    findings = []
    if run_job_calls:
        findings.append(f"{len(run_job_calls)} tRunJob call(s) detected — this job orchestrates child job(s).")
        if child_jobs:
            findings.append(f"Referenced child jobs: {', '.join(child_jobs)}.")
    else:
        findings.append("No tRunJob calls detected — this job does not orchestrate other jobs directly.")

    return {"findings": findings, "child_job_count": len(run_job_calls), "child_jobs": child_jobs}


# ── Transformation Architecture (Phase 6) ─────────────────────────────────────

_TMAP_FUNCS = re.compile(r"\bIF\s*\(|\bCASE\b|\bNVL\b|\bCOALESCE\b|\bSUBSTR\b|\bTO_DATE\b|\bTO_NUMBER\b|\bCONCAT\b", re.I)
_SURROGATE_RE = re.compile(r"sequence\.|nextval|surrogate|nextSequence", re.I)
_AGG_RE = re.compile(r"\bSUM\b|\bCOUNT\b|\bAVG\b|\bMAX\b|\bMIN\b|\bGROUP\b", re.I)


def generate_transformation_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    types = {c.get("component_type", "") for c in components}
    tmap_comps = [c for c in components if c.get("component_type") == "tMap"]
    tjava_comps = [c for c in components if c.get("component_type") in ("tJava", "tJavaRow", "tJavaFlex")]
    agg_comps = [c for c in components if c.get("component_type") in ("tAggregateRow", "tAggregateGroupBy")]

    tmap_expressions: list[str] = []
    surrogate_keys: list[str] = []
    context_vars: list[str] = []
    data_conversions: list[str] = []

    for m in job_data.get("column_mappings", []):
        expr = str(m.get("Expression", ""))
        if expr and expr not in ("", "—"):
            tmap_expressions.append(expr[:120])
        if _SURROGATE_RE.search(expr):
            surrogate_keys.append(m.get("Target Column", "?"))
        dtc = m.get("Data Type Conversion", "")
        if dtc and dtc not in ("", "—", "None"):
            data_conversions.append(dtc)
        if "context." in expr.lower():
            context_vars.append(expr[:80])

    findings = []
    if tmap_comps:
        findings.append(f"{len(tmap_comps)} tMap component(s) detected — primary transformation engine.")
        if tmap_expressions:
            sample = tmap_expressions[:3]
            findings.append(f"Sample tMap expressions: {'; '.join(sample)}")
        else:
            findings.append("No tMap column mapping expressions found (job may use pass-through mappings).")
    else:
        findings.append("No tMap components detected.")

    if tjava_comps:
        findings.append(f"{len(tjava_comps)} tJava/tJavaRow/tJavaFlex component(s) with custom Java logic detected.")
    if agg_comps:
        findings.append(f"{len(agg_comps)} aggregation component(s) detected: {', '.join(c.get('component_type','') for c in agg_comps)}.")
    if surrogate_keys:
        findings.append(f"Surrogate key generation patterns detected for: {', '.join(sorted(set(surrogate_keys))[:5])}.")
    if context_vars:
        findings.append(f"{len(context_vars)} tMap expression(s) reference context variables.")
    if data_conversions:
        findings.append(f"{len(set(data_conversions))} distinct data type conversion pattern(s) detected.")

    lookups = [c for c in components if c.get("component_type") == "tMap"
               and (c.get("parameters") or {}).get("LOOKUP_INPUT")]
    if lookups:
        findings.append(f"{len(lookups)} tMap(s) configured with lookup input flows.")
    filters = [r for r in job_data.get("mapping_rules", []) if r.get("Rule Type") == "Filter"]
    if filters:
        findings.append(f"{len(filters)} filter expression(s) detected in tMap outputs.")

    if not findings:
        findings.append("No transformation components detected.")

    return {
        "findings": findings,
        "tmap_count": len(tmap_comps),
        "tjava_count": len(tjava_comps),
        "surrogate_keys": surrogate_keys,
        "context_var_count": len(context_vars),
        "data_conversion_count": len(set(data_conversions)),
    }


# ── Job Flow Architecture (Phase 7) ───────────────────────────────────────────

def generate_job_flow_section(job_data: dict) -> dict:
    components = job_data.get("components", [])
    connections = job_data.get("connections", [])
    types = [c.get("component_type", "") for c in components]

    trigger_conns = [c for c in connections if _TRIGGER_RE.search(str(c.get("connector", "")))]
    data_conns = [c for c in connections if not _TRIGGER_RE.search(str(c.get("connector", "")))]
    run_jobs = [c for c in components if c.get("component_type") == "tRunJob"]

    findings = []
    findings.append(f"Total components: {len(components)}. Total connections: {len(connections)}.")
    findings.append(f"Data flow links: {len(data_conns)}. Trigger/control links: {len(trigger_conns)}.")
    if run_jobs:
        findings.append(f"{len(run_jobs)} tRunJob call(s) — this job spawns child jobs (orchestrator pattern).")
    else:
        findings.append("No tRunJob calls — single job execution, no child orchestration.")

    input_types = sorted({t for t in types if t.endswith("Input") or t == "tRowGenerator"})
    output_types = sorted({t for t in types if t.endswith("Output")})
    if input_types:
        findings.append(f"Entry points: {', '.join(input_types)}.")
    if output_types:
        findings.append(f"Exit points: {', '.join(output_types)}.")

    return {
        "findings": findings,
        "component_count": len(components),
        "trigger_link_count": len(trigger_conns),
        "data_link_count": len(data_conns),
    }


# ── Column Lineage (Phase 8) ──────────────────────────────────────────────────

def generate_column_lineage_section(job_data: dict) -> dict:
    mappings = job_data.get("column_mappings", [])
    findings = []

    if not mappings:
        findings.append("No tMap column-level mappings found — column lineage not available for this job.")
        return {"findings": findings, "lineage_rows": [], "total_columns": 0}

    lineage_rows = []
    for m in mappings:
        lineage_rows.append({
            "Source": f'{m.get("Source Component","")}.{m.get("Source Column","")}',
            "Transformation": m.get("Expression", "—"),
            "Target": f'{m.get("Target Component","")}.{m.get("Target Column","")}',
        })

    src_cols = len({f'{m.get("Source Component")}.{m.get("Source Column")}' for m in mappings})
    tgt_cols = len({f'{m.get("Target Component")}.{m.get("Target Column")}' for m in mappings})
    direct_mappings = sum(1 for m in mappings if not m.get("Expression") or m.get("Expression") in ("", "—"))
    transformed = len(mappings) - direct_mappings

    findings.append(f"{len(mappings)} column mapping(s) extracted from tMap components.")
    findings.append(f"{src_cols} unique source column reference(s), {tgt_cols} unique target column(s).")
    if transformed:
        findings.append(f"{transformed} column(s) involve expression-based transformations.")
    if direct_mappings:
        findings.append(f"{direct_mappings} column(s) are direct (pass-through) mappings.")

    return {"findings": findings, "lineage_rows": lineage_rows, "total_columns": len(mappings)}


# ── Canonical Section Provider Registry (F5.2 architecture) ───────────────────
# Maps section key -> SectionProvider callable. The orchestrator (tdd_export.py)
# iterates this registry instead of hardcoding per-section calls, so adding or
# removing a quality section requires no orchestrator edit.
def _build_section_registry() -> dict:
    return {
        "validation": generate_validation_section,
        "error_handling": generate_error_handling_section,
        "audit_monitoring": generate_audit_monitoring_section,
        "performance": generate_performance_section,
        "security": generate_security_section,
        "dependency": generate_dependency_section,
        "transformation": generate_transformation_section,
        "job_flow": generate_job_flow_section,
        "column_lineage": generate_column_lineage_section,
    }


def generate_all_sections(job_data: dict) -> dict:
    """Canonical entrypoint: run every registered SectionProvider for one job
    and return {section_key: result_dict}."""
    return {key: fn(job_data) for key, fn in _build_section_registry().items()}
