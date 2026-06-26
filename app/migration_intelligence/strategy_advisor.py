"""Evidence-driven migration strategy recommendations."""


class MigrationStrategyAdvisor:
    def recommend(self, complexity, readiness=None, effort=None):
        readiness = readiness or {}; effort = effort or {}
        level = complexity.get("complexity", "LOW")
        score = readiness.get("score", readiness.get("overall_score", readiness.get("migrationReadinessScore", 75)))
        jobs = complexity.get("jobs", [])
        unsupported = sum(j.get("factors", {}).get("unsupported_components", 0) for j in jobs)
        custom = sum(j.get("factors", {}).get("custom_java", 0) for j in jobs)
        if level == "CRITICAL" and (unsupported >= max(2, len(jobs)) or score < 35):
            strategy = "Rebuild"
            rationale = "Critical complexity and low platform compatibility make replacement safer than direct conversion."
        elif unsupported or score < 55:
            strategy = "Replatform"
            rationale = "Unsupported components or readiness gaps require target-native service and connector substitutions."
        elif level in {"HIGH", "CRITICAL"} or custom:
            strategy = "Refactor"
            rationale = "Complex orchestration and custom code should be simplified while preserving business behavior."
        else:
            strategy = "Lift-and-Shift"
            rationale = "High readiness and limited custom logic support a low-change migration path."
        return {"strategy": strategy, "rationale": rationale,
                "evidence": {"complexity": level, "readiness_score": score,
                             "unsupported_components": unsupported, "custom_java_components": custom,
                             "estimated_hours": effort.get("estimated_hours", 0)}}

    advise = recommend
