import re
from collections import defaultdict
from typing import Any, Dict, Sequence

from app.tiap.profiling.context_profiler import ContextProfiler


class ContextConsolidator:
    ENV_PREFIX = re.compile(r"^(DEV|QA|TEST|UAT|PROD|STG|SIT)[_-](.+)$", re.IGNORECASE)

    def analyze(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        profile = ContextProfiler().profile(all_jobs)
        groups = defaultdict(list)
        for context in profile.get("repository_context_matrix", {}).values():
            for name in context:
                match = self.ENV_PREFIX.match(name)
                canonical = match.group(2).upper() if match else re.sub(r"(HOST|SERVER)$", "HOST", name.upper())
                groups[canonical].append(name)
        opportunities = []
        for canonical, names in groups.items():
            unique = sorted(set(names))
            if len(unique) > 1:
                opportunities.append({"contexts": unique, "suggested_name": canonical, "recommendation": f"Consolidate as {canonical}"})
        return {"duplicate_contexts": profile.get("duplicate_contexts", []), "context_consolidation": opportunities}
