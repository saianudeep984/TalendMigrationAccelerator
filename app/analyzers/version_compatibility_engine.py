"""
VersionCompatibilityEngine

Resolves which target Talend versions a given source repository version
can be migrated to, based on the supported upgrade path, and surfaces
known deprecated/unsupported component notes for that hop.
"""

from typing import Any, Dict, List

from app.config.version_compatibility import VERSION_COMPATIBILITY
from app.config.version_matrix import VERSION_UPGRADE_MATRIX


class VersionCompatibilityEngine:
    """Resolves valid upgrade targets for a given Talend source version."""

    VERSION_ORDER: List[str] = [
        "Talend Open Studio",
        "Talend 6",
        "Talend 7",
        "Talend 7.3",
        "Talend 7.4",
        "Talend 8",
        "Talend Cloud",
    ]

    def is_known_version(self, version: str) -> bool:
        return version in self.VERSION_ORDER

    def get_supported_targets(self, source_version: str) -> List[Dict[str, Any]]:
        """
        Return all versions that source_version can be migrated to,
        in upgrade order, with hop count, upgrade path, and compatibility notes.
        """
        if not self.is_known_version(source_version):
            return []

        idx = self.VERSION_ORDER.index(source_version)
        targets: List[Dict[str, Any]] = []
        for i in range(idx + 1, len(self.VERSION_ORDER)):
            target_version = self.VERSION_ORDER[i]
            path = self.VERSION_ORDER[idx:i + 1]
            targets.append({
                "version": target_version,
                "direct": (i - idx) == 1,
                "hops": i - idx,
                "path": path,
                "notes": self._compatibility_notes(source_version, target_version),
            })
        return targets

    def _compatibility_notes(self, source_version: str, target_version: str) -> Dict[str, Any]:
        rules = VERSION_COMPATIBILITY.get(source_version, {})
        matrix_key = self._matrix_key(source_version, target_version)
        matrix_rules = VERSION_UPGRADE_MATRIX.get(matrix_key, {})
        return {
            "deprecated_components": rules.get("deprecated_components", []),
            "unsupported_components": rules.get("unsupported_components", []),
            "removed_components": matrix_rules.get("removed_components", []),
            "renamed_components": matrix_rules.get("renamed_components", {}),
        }

    @staticmethod
    def _matrix_key(source_version: str, target_version: str) -> str:
        src_num = "".join(c for c in source_version if c.isdigit())
        tgt_num = "".join(c for c in target_version if c.isdigit())
        return f"{src_num}_to_{tgt_num}" if src_num and tgt_num else ""


def generate_supported_target_versions(source_version: str) -> List[Dict[str, Any]]:
    """Convenience wrapper around VersionCompatibilityEngine.get_supported_targets."""
    return VersionCompatibilityEngine().get_supported_targets(source_version)
