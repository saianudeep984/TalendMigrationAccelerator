from typing import Any, Dict, Sequence

from app.tiap.testing.test_case_generator import TestCaseGenerator


class ValidationFramework:
    def build(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        generated = TestCaseGenerator().generate(all_jobs)
        tests = generated["test_cases"]
        readiness = min(100, int(len(tests) / max(1, len(all_jobs) * 8) * 100))
        return {
            "source_validation_tests": [t for t in tests if t["test_type"] == "Source Validation Tests"],
            "target_validation_tests": [t for t in tests if t["test_type"] == "Target Validation Tests"],
            "row_count_tests": [t for t in tests if t["test_type"] == "COUNT"],
            "null_checks": [t for t in tests if t["test_type"] == "NULL_CHECK"],
            "duplicate_checks": [t for t in tests if t["test_type"] == "DUPLICATE_CHECK"],
            "schema_validation": [t for t in tests if t["test_type"] == "Schema Validation"],
            "data_type_validation": [t for t in tests if t["test_type"] == "Data Type Validation"],
            "context_validation": [t for t in tests if t["test_type"] == "Context Validation"],
            "error_handling_validation": [t for t in tests if t["test_type"] == "Error Handling Validation"],
            "performance_validation": [t for t in tests if t["test_type"] == "Performance Validation"],
            "testing_readiness_score": readiness,
            "all_tests": tests,
        }
