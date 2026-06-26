"""
TMA Testing Architecture
Generates: Unit Tests, Validation SQL, Reconciliation Rules, Source vs Target Validation
Reuses: ai_test_generator, sql_assertion_generator, test_case_generator
"""
from __future__ import annotations
from typing import Any

from app.generators.ai_test_generator import generate_test_cases, _fallback_test_cases
from app.tiap.testing.sql_assertion_generator import SQLAssertionGenerator
from app.tiap.testing.test_case_generator import TestCaseGenerator
from app.parser.source_target_extractor import build_source_target_inventory


# ── Unit Tests ────────────────────────────────────────────────────────────────

def generate_unit_tests(job_data: dict) -> list[dict]:
    """Rule-based unit tests per component."""
    cases = _fallback_test_cases(job_data)
    inv = build_source_target_inventory(job_data)
    unit = []
    for c in job_data.get("components", []):
        ctype = c.get("component_type", "")
        cname = c.get("component_name", ctype)
        unit.append({
            "suite": "Unit",
            "tc_id": f"UT_{job_data['job_name']}_{cname}",
            "component": cname,
            "type": ctype,
            "objective": f"Verify {cname} ({ctype}) executes without error",
            "steps": [
                f"1. Isolate component {cname} in test harness.",
                "2. Inject mock input with 10 representative rows.",
                "3. Execute component.",
                "4. Assert output row count equals input row count (or business rule).",
                "5. Assert no exception thrown.",
            ],
            "expected": "Component processes rows and passes output downstream.",
            "priority": "HIGH" if "Output" in ctype or "Input" in ctype else "MEDIUM",
        })
    # Append category test cases from ai_test_generator
    for tc in cases:
        unit.append({
            "suite": "Unit",
            "tc_id": tc["tc_id"],
            "component": "Job",
            "type": tc["category"],
            "objective": tc["objective"],
            "steps": tc["steps"],
            "expected": tc["expected_result"],
            "priority": tc["priority"],
        })
    return unit


# ── Validation SQL ────────────────────────────────────────────────────────────

def generate_validation_sql(job_data: dict) -> list[dict]:
    gen = SQLAssertionGenerator()
    tcg = TestCaseGenerator()
    inv = build_source_target_inventory(job_data)
    results = []

    targets = inv["target_names"] if inv["target_names"] != ["(none detected)"] else [job_data["job_name"]]
    sources = inv["source_names"] if inv["source_names"] != ["(none detected)"] else ["SOURCE"]

    for tbl in targets:
        for a in gen.generate_for_table(tbl):
            results.append({
                "table": tbl,
                "type": a["type"],
                "sql": a["sql"],
                "description": _sql_desc(a["type"]),
            })

    # Source-side assertions
    for tbl in sources:
        results.append({
            "table": tbl,
            "type": "SOURCE_COUNT",
            "sql": f"SELECT COUNT(*) AS src_count FROM {tbl};",
            "description": "Pre-load source row count for reconciliation baseline.",
        })
        results.append({
            "table": tbl,
            "type": "NULL_KEY_CHECK",
            "sql": f"SELECT COUNT(*) FROM {tbl} WHERE ID IS NULL;",
            "description": "Ensure no null primary keys before load.",
        })

    return results


def _sql_desc(t):
    return {
        "COUNT": "Validate total rows loaded into target.",
        "MIN_MAX": "Verify key range integrity.",
        "HASH_VALIDATION": "Checksum-based data integrity check.",
        "DUPLICATE_CHECK": "Detect duplicate primary keys.",
        "NULL_CHECK": "Identify unexpected nulls in critical columns.",
    }.get(t, "Validation assertion.")


# ── Reconciliation Rules ──────────────────────────────────────────────────────

def generate_reconciliation_rules(job_data: dict) -> list[dict]:
    inv = build_source_target_inventory(job_data)
    jname = job_data["job_name"]
    sources = inv["source_names"] if inv["source_names"] != ["(none detected)"] else ["SOURCE"]
    targets = inv["target_names"] if inv["target_names"] != ["(none detected)"] else ["TARGET"]

    rules = []
    for src, tgt in zip(sources, targets):
        rules += [
            {
                "rule_id": f"RECON_{jname}_01",
                "name": "Row Count Match",
                "source": src,
                "target": tgt,
                "sql_source": f"SELECT COUNT(*) FROM {src};",
                "sql_target": f"SELECT COUNT(*) FROM {tgt};",
                "logic": "ABS(src_count - tgt_count) = 0",
                "tolerance": "0%",
                "severity": "CRITICAL",
            },
            {
                "rule_id": f"RECON_{jname}_02",
                "name": "Numeric Sum Match",
                "source": src,
                "target": tgt,
                "sql_source": f"SELECT SUM(AMOUNT) FROM {src};",
                "sql_target": f"SELECT SUM(AMOUNT) FROM {tgt};",
                "logic": "ABS(src_sum - tgt_sum) / NULLIF(src_sum,0) < 0.001",
                "tolerance": "0.1%",
                "severity": "HIGH",
            },
            {
                "rule_id": f"RECON_{jname}_03",
                "name": "Date Range Integrity",
                "source": src,
                "target": tgt,
                "sql_source": f"SELECT MIN(LOAD_DATE), MAX(LOAD_DATE) FROM {src};",
                "sql_target": f"SELECT MIN(LOAD_DATE), MAX(LOAD_DATE) FROM {tgt};",
                "logic": "src_min_date = tgt_min_date AND src_max_date = tgt_max_date",
                "tolerance": "Exact",
                "severity": "HIGH",
            },
            {
                "rule_id": f"RECON_{jname}_04",
                "name": "Orphan Record Check",
                "source": src,
                "target": tgt,
                "sql_source": f"SELECT ID FROM {src} WHERE ID NOT IN (SELECT ID FROM {tgt});",
                "sql_target": f"SELECT ID FROM {tgt} WHERE ID NOT IN (SELECT ID FROM {src});",
                "logic": "Result sets must be empty",
                "tolerance": "0 orphans",
                "severity": "CRITICAL",
            },
            {
                "rule_id": f"RECON_{jname}_05",
                "name": "Hash Checksum",
                "source": src,
                "target": tgt,
                "sql_source": f"SELECT SUM(ORA_HASH(ID)) FROM {src};",
                "sql_target": f"SELECT SUM(ORA_HASH(ID)) FROM {tgt};",
                "logic": "src_hash = tgt_hash",
                "tolerance": "Exact",
                "severity": "CRITICAL",
            },
        ]
    return rules


# ── Source vs Target Validation ───────────────────────────────────────────────

def generate_src_vs_tgt(job_data: dict) -> list[dict]:
    inv = build_source_target_inventory(job_data)
    jname = job_data["job_name"]
    sources = inv["source_names"] if inv["source_names"] != ["(none detected)"] else ["SOURCE"]
    targets = inv["target_names"] if inv["target_names"] != ["(none detected)"] else ["TARGET"]

    checks = []
    for src, tgt in zip(sources, targets):
        checks += [
            {
                "check_id": f"SVT_{jname}_01",
                "category": "Row Count",
                "source_query": f"SELECT COUNT(*) AS cnt FROM {src}",
                "target_query": f"SELECT COUNT(*) AS cnt FROM {tgt}",
                "pass_condition": "src.cnt == tgt.cnt",
                "on_fail": "Flag as MISMATCH — investigate dropped/duplicate rows",
            },
            {
                "check_id": f"SVT_{jname}_02",
                "category": "Column Nullability",
                "source_query": f"SELECT COUNT(*) FROM {src} WHERE ID IS NULL OR KEY_COL IS NULL",
                "target_query": f"SELECT COUNT(*) FROM {tgt} WHERE ID IS NULL OR KEY_COL IS NULL",
                "pass_condition": "Both return 0",
                "on_fail": "NULL propagation issue in transformation",
            },
            {
                "check_id": f"SVT_{jname}_03",
                "category": "Data Type Integrity",
                "source_query": f"SELECT TYPEOF(AMOUNT), TYPEOF(LOAD_DATE) FROM {src} LIMIT 1",
                "target_query": f"SELECT TYPEOF(AMOUNT), TYPEOF(LOAD_DATE) FROM {tgt} LIMIT 1",
                "pass_condition": "Types match across source and target",
                "on_fail": "Type casting error in tMap or conversion component",
            },
            {
                "check_id": f"SVT_{jname}_04",
                "category": "Aggregation Totals",
                "source_query": f"SELECT SUM(AMOUNT), AVG(AMOUNT) FROM {src}",
                "target_query": f"SELECT SUM(AMOUNT), AVG(AMOUNT) FROM {tgt}",
                "pass_condition": "Variance < 0.1%",
                "on_fail": "Aggregation or filter logic mismatch",
            },
            {
                "check_id": f"SVT_{jname}_05",
                "category": "Schema Column Parity",
                "source_query": f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{src}' ORDER BY ORDINAL_POSITION",
                "target_query": f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{tgt}' ORDER BY ORDINAL_POSITION",
                "pass_condition": "Column lists are identical (or mapped per lineage spec)",
                "on_fail": "Missing or extra columns — review column mapping",
            },
            {
                "check_id": f"SVT_{jname}_06",
                "category": "Sample Row Comparison",
                "source_query": f"SELECT * FROM {src} ORDER BY ID FETCH FIRST 100 ROWS ONLY",
                "target_query": f"SELECT * FROM {tgt} ORDER BY ID FETCH FIRST 100 ROWS ONLY",
                "pass_condition": "Row-by-row comparison returns 0 differences",
                "on_fail": "Value-level transformation error",
            },
        ]
    return checks


# ── Master Builder ────────────────────────────────────────────────────────────

def build_testing_architecture(job_data: dict) -> dict:
    return {
        "job_name": job_data.get("job_name", "Unknown"),
        "unit_tests": generate_unit_tests(job_data),
        "validation_sql": generate_validation_sql(job_data),
        "reconciliation_rules": generate_reconciliation_rules(job_data),
        "src_vs_tgt": generate_src_vs_tgt(job_data),
    }
