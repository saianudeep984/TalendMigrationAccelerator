"""
Repository Health Scorer
Scores health of the uploaded Open Studio ZIP before migration.

Uses the canonical Health Engine thresholds:
    score >= 80  → GREEN  (HEALTHY)
    score >= 60  → AMBER  (AT RISK)
    score <  60  → RED    (CRITICAL)

overall_status always returns GREEN / AMBER / RED (no custom labels).
"""

from app.analyzers.health_score import rag_from_score


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
        item_files = [f for f in file_list if f.endswith(".item")]

        if job_count == 0:
            warnings.append("No job .item files found")

        # --- Check for contexts ---
        context_files = [f for f in file_list if "context" in f.lower()]
        if not context_files:
            warnings.append(
                "No context files detected — context variables may be missing"
            )

        # --- Check for routines ---
        routine_files = [f for f in file_list if "routines" in f.lower()]
        if not routine_files:
            warnings.append("No routine files detected")

        # --- Score Calculation (canonical thresholds: >=80 GREEN / >=60 AMBER / <60 RED) ---
        if errors > 0:
            score = 0
        elif len(warnings) > 2:
            score = 40
        elif len(warnings) > 0:
            score = 70
        else:
            score = 100

        overall_status = rag_from_score(score)

        # Friendly display label (display-only, never used for scoring logic)
        _status_label = {
            "GREEN": "✅ HEALTHY",
            "AMBER": "🟡 AT RISK",
            "RED":   "🔴 CRITICAL",
        }.get(overall_status, overall_status)

        return {
            # Canonical keys consumed by all pages
            "overall_score":   score,
            "overall_status":  overall_status,
            # Display-only label (Health Engine status text)
            "health_status":   _status_label,
            "errors":          errors,
            "warnings":        warnings,
            "job_count":       job_count,
            "item_files":      len(item_files),
            "context_files":   len(context_files),
            "routine_files":   len(routine_files),
            "ready_for_migration": errors == 0,
        }
