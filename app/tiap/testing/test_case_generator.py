from typing import Any, Dict, Sequence

from app.tiap.models.repository import component_parameters
from app.tiap.testing.sql_assertion_generator import SQLAssertionGenerator


class TestCaseGenerator:
    def generate(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        cases = []
        sql = SQLAssertionGenerator()
        for job in all_jobs:
            data = job.get("job_data", {})
            job_name = data.get("job_name", "Unknown")
            targets = self._target_tables(data)
            cases.extend([
                self._case(job_name, "Source Validation Tests", "Validate source connectivity and source row availability."),
                self._case(job_name, "Target Validation Tests", "Validate target connectivity and write permissions."),
                self._case(job_name, "Context Validation", "Validate required context variables for selected environment."),
                self._case(job_name, "Error Handling Validation", "Validate error paths, reject flows, and logging components."),
                self._case(job_name, "Performance Validation", "Validate runtime SLA and throughput for production volume."),
            ])
            for table in targets or [job_name]:
                for assertion in sql.generate_for_table(table):
                    cases.append(self._case(job_name, assertion["type"], assertion["sql"]))
            cases.append(self._case(job_name, "Schema Validation", "Compare source and target schema column names and data types."))
            cases.append(self._case(job_name, "Data Type Validation", "Validate numeric, date, and string conversion behavior."))
        return {"test_cases": cases, "test_case_count": len(cases)}

    def _target_tables(self, data):
        targets = []
        for component in data.get("components", []):
            ctype = component.get("component_type", "")
            if "Output" not in ctype and not ctype.endswith("Row"):
                continue
            params = component_parameters(component)
            table = params.get("TABLE") or params.get("TABLE_NAME") or params.get("DBTABLE") or params.get("FILE_NAME")
            if table:
                targets.append(str(table).strip('"').strip("'"))
        return sorted(set(targets))

    def _case(self, job_name, test_type, expected):
        return {"job": job_name, "test_type": test_type, "expected_result": expected, "priority": "HIGH" if "Validation" in test_type else "MEDIUM"}
