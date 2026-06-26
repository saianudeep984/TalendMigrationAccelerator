"""Unified architecture scorecard; consumes shared readiness/complexity signals."""
from __future__ import annotations

from typing import Any, Dict


def clamp(value) -> int:
    return max(0, min(100, int(round(value))))


def rag(score: int) -> str:
    return "GREEN" if score >= 80 else "AMBER" if score >= 60 else "RED"


class ArchitectureScorecard:
    WEIGHTS = {
        "architecture_quality": 0.22,
        "maintainability": 0.18,
        "scalability": 0.16,
        "reusability": 0.14,
        "migration_readiness": 0.20,
        "technical_debt_inverse": 0.10,
    }

    def build(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        anti = signals.get("anti_patterns", {})
        complexity = (signals.get("migration_intelligence") or {}).get("complexity", {})
        readiness = signals.get("readiness") or {}
        structure = signals.get("structure", {})
        debt = signals.get("technical_debt", {})

        anti_penalty = min(70, anti.get("risk_score", 0) * 0.7)
        complexity_penalty = min(45, complexity.get("score", 0) * 0.25)
        readiness_score = readiness.get("overall_score", readiness.get("score", readiness.get("migration_readiness_score", 0))) or 0
        reuse_ratio = structure.get("joblet_ratio", 0)
        metadata_ratio = structure.get("metadata_ratio", 0)
        context_ratio = structure.get("context_ratio", 0)

        scores = {
            "architecture_quality_score": clamp(100 - anti_penalty - complexity_penalty + metadata_ratio * 15),
            "maintainability_score": clamp(100 - anti_penalty - structure.get("inline_java_ratio", 0) * 35 + context_ratio * 10),
            "scalability_score": clamp(100 - complexity_penalty - structure.get("deep_chain_penalty", 0) + metadata_ratio * 10),
            "reusability_score": clamp(55 + reuse_ratio * 35 + metadata_ratio * 15 - anti.get("summary", {}).get("duplicate_job_logic", 0) * 8),
            "migration_readiness_score": clamp(readiness_score),
            "technical_debt_score": clamp(debt.get("technical_debt_score", anti.get("risk_score", 0))),
        }
        overall = clamp(
            scores["architecture_quality_score"] * self.WEIGHTS["architecture_quality"]
            + scores["maintainability_score"] * self.WEIGHTS["maintainability"]
            + scores["scalability_score"] * self.WEIGHTS["scalability"]
            + scores["reusability_score"] * self.WEIGHTS["reusability"]
            + scores["migration_readiness_score"] * self.WEIGHTS["migration_readiness"]
            + (100 - scores["technical_debt_score"]) * self.WEIGHTS["technical_debt_inverse"]
        )
        scores.update({"overall_architecture_maturity_score": overall, "rag": rag(overall), "weights": self.WEIGHTS})
        return scores

