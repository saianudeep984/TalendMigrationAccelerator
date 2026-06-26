"""
Repository Health Scorer
Scores health of the uploaded Open Studio ZIP before migration.
"""


class RepositoryHealth:

    def score(
        self,
        validation_errors: list,
        job_count: int,
        file_list: list
    ) -> dict:

        errors = len(validation_errors)

        warnings = []

        # --- Check for empty items ---
        item_files = [
            f for f in file_list
            if f.endswith(".item")
        ]

        if job_count == 0:
            warnings.append(
                "No job .item files found"
            )

        # --- Check for contexts ---
        context_files = [
            f for f in file_list
            if "context" in f.lower()
        ]

        if not context_files:
            warnings.append(
                "No context files detected — "
                "context variables may be missing"
            )

        # --- Check for routines ---
        routine_files = [
            f for f in file_list
            if "routines" in f.lower()
        ]

        if not routine_files:
            warnings.append(
                "No routine files detected"
            )

        # --- Score Calculation ---
        if errors > 0:
            health = "❌ CRITICAL"
            score = 0
        elif len(warnings) > 2:
            health = "⚠️ AT RISK"
            score = 40
        elif len(warnings) > 0:
            health = "🟡 FAIR"
            score = 70
        else:
            health = "✅ HEALTHY"
            score = 100

        return {
            "health_status": health,
            "score": score,
            "errors": errors,
            "warnings": warnings,
            "job_count": job_count,
            "item_files": len(item_files),
            "context_files": len(context_files),
            "routine_files": len(routine_files),
            "ready_for_migration": errors == 0
        }
