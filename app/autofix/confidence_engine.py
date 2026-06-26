"""Confidence scoring for architecture and auto-fix intelligence."""
from __future__ import annotations

from typing import Any, Dict


class ConfidenceScoringEngine:
    def score(self, jobs, architecture=None, autofix=None, impact=None, migration_intelligence=None, readiness=None) -> Dict[str, Any]:
        jobs = list(jobs or [])
        analyzed = sum(1 for j in jobs if isinstance(j, dict) and (j.get("job_data") or j.get("estimation") or j.get("dependencies")))
        coverage = analyzed / max(1, len(jobs))
        has_components = sum(1 for j in jobs for _ in ((j.get("job_data", j) if isinstance(j, dict) else {}).get("components", []) or []))
        lineage_edges = len((impact or {}).get("lineage", {}).get("edges", []))
        rules = len((autofix or {}).get("component_rules", {}).get("findings", []))
        anti = len((architecture or {}).get("anti_patterns", {}).get("findings", []))
        scores = {
            "version_detection_confidence": self._band(70 + min(20, has_components)),
            "readiness_confidence": self._band(60 + coverage * 35 + (10 if readiness else 0)),
            "complexity_confidence": self._band(65 + coverage * 30 + (5 if migration_intelligence else 0)),
            "lineage_confidence": self._band(50 + min(40, lineage_edges * 3)),
            "auto_fix_confidence": self._band(55 + min(35, rules * 7)),
            "architecture_analysis_confidence": self._band(60 + coverage * 25 + min(15, anti * 2)),
        }
        overall = int(sum(v["score"] for v in scores.values()) / len(scores))
        return {"scores": scores, "overall_confidence": overall, "overall_band": self._label(overall)}

    @classmethod
    def _band(cls, value):
        score = max(0, min(100, int(value)))
        return {"score": score, "band": cls._label(score)}

    @staticmethod
    def _label(score):
        return "HIGH" if score >= 80 else "MEDIUM" if score >= 60 else "LOW"

