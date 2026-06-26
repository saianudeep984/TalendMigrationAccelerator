"""
TargetVersionRecommendationEngine  (F9.3)

Recommends the best Talend 8.x target version for a 7.x source repository.
Builds on VersionCompatibilityEngine (valid targets) and UpgradePathAnalyzer
(per-hop component impact) to rank candidates by upgrade risk, then applies
enterprise-feature signals to prefer Talend Cloud when warranted.
"""

from typing import Any, Dict, List, Optional

from app.analyzers.version_compatibility_engine import VersionCompatibilityEngine
from app.analyzers.version_upgrade_analyzer import UpgradePathAnalyzer

SEVEN_X_VERSIONS = ["Talend 7", "Talend 7.3", "Talend 7.4"]
EIGHT_X_VERSIONS = ["Talend 8", "Talend Cloud"]


class TargetVersionRecommendationEngine:
    """Recommends a target version for Talend 7.x -> 8.x migrations."""

    def __init__(self, compatibility_engine=None, upgrade_analyzer=None):
        self.compatibility_engine = compatibility_engine or VersionCompatibilityEngine()
        self.upgrade_analyzer = upgrade_analyzer or UpgradePathAnalyzer()

    def is_supported_source(self, source_version: str) -> bool:
        return source_version in SEVEN_X_VERSIONS

    def recommend(
        self,
        source_version: str,
        component_usage: Optional[List[str]] = None,
        enterprise_features: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Return a recommendation dict:
        {
            "sourceVersion", "supported", "recommendedTarget",
            "confidence", "rationale", "candidates": [...]
        }
        """
        if not self.is_supported_source(source_version):
            return {
                "sourceVersion": source_version,
                "supported": False,
                "recommendedTarget": None,
                "confidence": "NONE",
                "rationale": "F9.3 only covers Talend 7.x to 8.x paths.",
                "candidates": [],
            }

        component_usage = component_usage or []
        enterprise_features = enterprise_features or {}

        candidates = []
        for target in EIGHT_X_VERSIONS:
            candidates.append(self._score_candidate(source_version, target, component_usage))

        wants_cloud = bool(enterprise_features.get("summary"))
        candidates.sort(key=lambda c: (c["riskScore"], c["hops"]))

        best = candidates[0]
        if wants_cloud:
            cloud = next((c for c in candidates if c["targetVersion"] == "Talend Cloud"), None)
            if cloud:
                best = cloud

        rationale = self._build_rationale(best, wants_cloud)

        return {
            "sourceVersion": source_version,
            "supported": True,
            "recommendedTarget": best["targetVersion"],
            "confidence": self._confidence(best["riskScore"]),
            "rationale": rationale,
            "candidates": candidates,
        }

    def _score_candidate(self, source_version: str, target_version: str, component_usage: List[str]) -> Dict[str, Any]:
        path_report = self.upgrade_analyzer.analyze_path(source_version, target_version)
        removed = set(path_report.get("removedComponents", []))
        renamed = set(path_report.get("renamedComponents", {}).keys())

        removed_hits = sum(1 for c in component_usage if c in removed)
        renamed_hits = sum(1 for c in component_usage if c in renamed)
        hops = len(path_report.get("hops", []))
        supported = path_report.get("supported", False)

        risk_score = removed_hits * 3 + renamed_hits * 1 + hops
        if not supported:
            # No direct numeric upgrade path resolved (e.g. Talend Cloud).
            # Penalize so it is only chosen on an explicit signal override.
            risk_score += 5

        return {
            "targetVersion": target_version,
            "hops": hops,
            "supported": path_report.get("supported", False),
            "removedHits": removed_hits,
            "renamedHits": renamed_hits,
            "riskScore": risk_score,
        }

    @staticmethod
    def _confidence(risk_score: int) -> str:
        if risk_score == 0:
            return "HIGH"
        if risk_score <= 3:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _build_rationale(best: Dict[str, Any], wants_cloud: bool) -> str:
        parts = [f"{best['targetVersion']} reached in {best['hops']} hop(s)."]
        if best["removedHits"]:
            parts.append(f"{best['removedHits']} component(s) in use are removed on this path.")
        if best["renamedHits"]:
            parts.append(f"{best['renamedHits']} component(s) in use are renamed on this path.")
        if wants_cloud:
            parts.append("Enterprise features detected; Talend Cloud preferred where viable.")
        return " ".join(parts)


def recommend_target_version(
    source_version: str,
    component_usage: Optional[List[str]] = None,
    enterprise_features: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper around TargetVersionRecommendationEngine.recommend."""
    return TargetVersionRecommendationEngine().recommend(source_version, component_usage, enterprise_features)
