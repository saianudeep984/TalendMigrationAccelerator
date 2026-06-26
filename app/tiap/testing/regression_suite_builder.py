import csv
import os
from typing import Any, Dict, Sequence

import pandas as pd

from app.tiap.documentation.export_utils import write_pdf
from app.tiap.models.repository import write_json
from app.tiap.testing.validation_framework import ValidationFramework


class RegressionSuiteBuilder:
    def build(self, all_jobs: Sequence[Dict[str, Any]], output_dir: str = None) -> Dict[str, Any]:
        suite = ValidationFramework().build(all_jobs)
        result = {"regression_suite": suite, "testing_readiness_score": suite["testing_readiness_score"]}
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            write_json(os.path.join(output_dir, "testing_suite.json"), result)
            self.export(result, output_dir)
        return result

    def export(self, suite: Dict[str, Any], output_dir: str) -> Dict[str, str]:
        tests = suite.get("regression_suite", {}).get("all_tests", [])
        paths = {
            "csv": os.path.join(output_dir, "testing_suite.csv"),
            "excel": os.path.join(output_dir, "testing_suite.xlsx"),
            "pdf": os.path.join(output_dir, "testing_suite.pdf"),
        }
        with open(paths["csv"], "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["job", "test_type", "expected_result", "priority"])
            writer.writeheader()
            writer.writerows(tests)
        pd.DataFrame(tests).to_excel(paths["excel"], index=False)
        write_pdf(paths["pdf"], "\n".join(f"{t['job']} - {t['test_type']} - {t['expected_result']}" for t in tests))
        return paths
