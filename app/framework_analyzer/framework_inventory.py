from __future__ import annotations
from .framework_detector import FrameworkDetectionEngine


class FrameworkInventoryEngine:
    def inventory(self, jobs):
        detected = FrameworkDetectionEngine().detect(jobs)
        total = len(detected)
        used = sum(1 for x in detected.values() if x["detected"])
        return {"framework_inventory": detected, "framework_usage": {k: v["usage_count"] for k, v in detected.items()},
                "framework_coverage": round(used / max(1, total) * 100, 1),
                "framework_dependencies": [{"framework": k, "depends_on": ["context_framework", "logging_framework"]} for k, v in detected.items() if v["detected"] and k not in {"context_framework", "logging_framework"}]}
