from app.ai.context_accessor import get_ai_context
from app.parser.source_target_extractor import build_source_target_inventory
from app.tiap.testing.test_case_generator import TestCaseGenerator


_TEST_CATEGORIES = [
    "Source Validation",
    "Target Validation",
    "Row Count Validation",
    "Context Validation",
    "Error Handling",
    "Performance Test",
    "Regression Test",
]


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def _build_test_prompt(job_data: dict) -> str:
    components = [c["component_type"] for c in job_data.get("components", [])]
    db_in  = [c for c in components if "Input"  in c]
    db_out = [c for c in components if "Output" in c]
    contexts = list(job_data.get("contexts", {}).keys())
    inv = build_source_target_inventory(job_data)
    return (
        f"You are a Talend QA engineer. Generate test cases for the following job.\n"
        f"Job Name: {job_data['job_name']}\n"
        f"Source Tables/Files : {', '.join(inv['source_names'])}\n"
        f"Target Tables/Files : {', '.join(inv['target_names'])}\n"
        f"Input Components    : {', '.join(db_in)  or 'None'}\n"
        f"Output Components   : {', '.join(db_out) or 'None'}\n"
        f"Context Groups      : {', '.join(contexts) or 'None'}\n\n"
        "Generate 7 test cases (one per category): "
        "Source Validation, Target Validation, Row Count Validation, "
        "Context Validation, Error Handling, Performance Test, Regression Test.\n\n"
        "Format each as:\n"
        "TEST CASE: <category>\n"
        "Objective: <what to verify>\n"
        "Steps: <numbered steps>\n"
        "Expected Result: <expected outcome>\n\n"
        "Keep each test case concise and practical."
    )


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

def _fallback_test_cases(job_data: dict) -> list[dict]:
    jname      = job_data["job_name"]
    components = [c["component_type"] for c in job_data.get("components", [])]
    inv        = build_source_target_inventory(job_data)
    db_in      = inv["source_names"][0] if inv["source_names"] != ["(none detected)"] else \
                 next((c for c in components if "Input"  in c), "Source System")
    db_out     = inv["target_names"][0] if inv["target_names"] != ["(none detected)"] else \
                 next((c for c in components if "Output" in c), "Target System")
    raw_contexts = job_data.get("contexts", [])

    if isinstance(raw_contexts, dict):
        contexts = list(raw_contexts.keys())
    elif isinstance(raw_contexts, list):
        contexts = []
        for c in raw_contexts:
            if isinstance(c, dict):
                contexts.append(c.get("name") or c.get("label") or c.get("context") or "Default")
            else:
                contexts.append(str(c))
    else:
        contexts = []

    ctx_name = contexts[0] if contexts else "Default"

    return [
        {
            "category":       "Source Validation",
            "tc_id":          f"TC_{jname}_01",
            "objective":      f"Verify {db_in} returns expected data",
            "steps":          [
                f"1. Connect to source using {db_in} configuration.",
                "2. Run source query with boundary date parameters.",
                "3. Validate row count against source system count.",
                "4. Verify data types and formats match schema.",
            ],
            "expected_result": "Row count matches source. All columns populate correctly.",
            "priority":        "HIGH",
        },
        {
            "category":       "Target Validation",
            "tc_id":          f"TC_{jname}_02",
            "objective":      f"Verify data is correctly written to {db_out}",
            "steps":          [
                "1. Execute job with test context.",
                f"2. Query target using {db_out} connection.",
                "3. Compare source and target record counts.",
                "4. Spot-check 5 random records for data accuracy.",
            ],
            "expected_result": "Target data matches source data. No duplicates or missing records.",
            "priority":        "HIGH",
        },
        {
            "category":       "Row Count Validation",
            "tc_id":          f"TC_{jname}_03",
            "objective":      "Ensure no records are dropped during transformation",
            "steps":          [
                "1. Record source row count before job run.",
                "2. Execute the job.",
                "3. Record target row count after job run.",
                "4. Compare source vs target count.",
            ],
            "expected_result": "Source count equals target count (or matches business rule for filtered rows).",
            "priority":        "HIGH",
        },
        {
            "category":       "Context Validation",
            "tc_id":          f"TC_{jname}_04",
            "objective":      f"Verify context group '{ctx_name}' variables load correctly",
            "steps":          [
                f"1. Launch job with context group: {ctx_name}.",
                "2. Log context variable values at startup.",
                "3. Verify connection strings are valid.",
                "4. Verify date parameters are within expected range.",
            ],
            "expected_result": f"All context variables from '{ctx_name}' load without error.",
            "priority":        "MEDIUM",
        },
        {
            "category":       "Error Handling",
            "tc_id":          f"TC_{jname}_05",
            "objective":      "Verify job handles errors gracefully",
            "steps":          [
                "1. Simulate source system unavailability.",
                "2. Run the job and observe error output.",
                "3. Verify error is logged with clear message.",
                "4. Verify job exits with non-zero code.",
                "5. Confirm no partial writes to target.",
            ],
            "expected_result": "Job fails cleanly with error logged. No corrupt data written to target.",
            "priority":        "HIGH",
        },
        {
            "category":       "Performance Test",
            "tc_id":          f"TC_{jname}_06",
            "objective":      "Verify job completes within acceptable SLA",
            "steps":          [
                "1. Load full production-volume dataset.",
                "2. Start job and record start time.",
                "3. Monitor memory and CPU during execution.",
                "4. Record completion time.",
            ],
            "expected_result": "Job completes within defined SLA. Memory stays below 80% threshold.",
            "priority":        "MEDIUM",
        },
        {
            "category":       "Regression Test",
            "tc_id":          f"TC_{jname}_07",
            "objective":      "Verify post-migration job produces same output as pre-migration",
            "steps":          [
                "1. Capture pre-migration output (row count, checksums, samples).",
                "2. Migrate job to Talend 8.",
                "3. Execute migrated job with same inputs.",
                "4. Compare output against pre-migration baseline.",
            ],
            "expected_result": "Migrated job output matches pre-migration baseline within 0% variance.",
            "priority":        "CRITICAL",
        },
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_test_cases(job_data: dict, use_ai: bool = False) -> list[dict]:
    """
    Returns a list of test case dicts. Consumes cached AI context when available.
    Falls back to rule-based generation — no direct Ollama calls.
    use_ai=False (default) uses reliable rule-based generation.
    """
    if use_ai:
        ctx = get_ai_context()
        ctx_tests = ctx.get("test_cases", "")
        if ctx_tests:
            cases = _parse_ai_test_output(str(ctx_tests), job_data["job_name"])
            if cases:
                return cases

    generated = TestCaseGenerator().generate([{"job_data": job_data}])
    cases = []
    for index, test in enumerate(generated.get("test_cases", []), start=1):
        test_type = test.get("test_type", "Validation")
        cases.append({
            "category": test_type,
            "tc_id": f"TC_{job_data['job_name']}_{index:02d}",
            "objective": test.get("expected_result", test_type),
            "steps": ["Execute the job with the selected context.", "Validate the generated assertion or expected result."],
            "expected_result": test.get("expected_result", "Job behaves as expected."),
            "priority": test.get("priority", "MEDIUM"),
        })
    return cases or _fallback_test_cases(job_data)


def _parse_ai_test_output(raw: str, job_name: str) -> list[dict]:
    """Best-effort parser for AI free-text test cases."""
    cases  = []
    blocks = raw.split("TEST CASE:")
    for i, block in enumerate(blocks[1:], 1):
        lines = block.strip().splitlines()
        category = lines[0].strip() if lines else f"Test {i}"
        obj_line = next((l for l in lines if l.startswith("Objective:")), "")
        exp_line = next((l for l in lines if l.startswith("Expected Result:")), "")
        objective = obj_line.replace("Objective:", "").strip()
        expected  = exp_line.replace("Expected Result:", "").strip()

        steps_raw = []
        in_steps  = False
        for line in lines:
            if line.startswith("Steps:"):
                in_steps = True
                continue
            if in_steps and line.startswith("Expected"):
                in_steps = False
            if in_steps and line.strip():
                steps_raw.append(line.strip())

        cases.append({
            "category":       category,
            "tc_id":          f"TC_{job_name}_{i:02d}",
            "objective":      objective or "See description",
            "steps":          steps_raw or ["Execute test as described."],
            "expected_result": expected or "Job behaves as expected.",
            "priority":       "MEDIUM",
        })
    return cases