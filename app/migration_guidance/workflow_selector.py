"""
WorkflowSelector  (F9.4)

Dynamically selects a migration workflow (ordered step list) based on the
detected ProjectType (Open Studio / Enterprise / Cloud) and the migration
path (source_version -> target_version), reusing UpgradePathAnalyzer for
hop count so multi-hop paths get an extra "intermediate upgrade" step.
"""

from typing import Any, Dict, List, Optional

from app.parser.project_classifier import ProjectType
from app.analyzers.version_upgrade_analyzer import UpgradePathAnalyzer

_BASE_STEPS = {
    ProjectType.OPEN_STUDIO: [
        "Upload Open Studio repository",
        "Analyze compatibility",
        "Generate migration workspace",
        "Import into Talend 8",
        "Validate migrated jobs",
    ],
    ProjectType.ENTERPRISE: [
        "Export repository from TAC",
        "Analyze compatibility and enterprise feature usage",
        "Generate migration workspace",
        "Import into Talend 8 Enterprise",
        "Re-publish jobs to Job Servers",
        "Validate migrated jobs",
    ],
    ProjectType.CLOUD: [
        "Export workspace from Talend Cloud project",
        "Analyze compatibility and Cloud engine dependencies",
        "Generate migration workspace",
        "Import into target Talend Cloud workspace",
        "Reconfigure Remote Engines / connections",
        "Validate migrated jobs",
    ],
}

_INTERMEDIATE_HOP_STEP = "Perform intermediate version upgrade before final target"
_CLOUD_FINAL_STEP = "Perform cloud optimization"


class WorkflowSelector:
    """Selects an ordered workflow step list for a project type + migration path."""

    def __init__(self, upgrade_analyzer: Optional[UpgradePathAnalyzer] = None):
        self.upgrade_analyzer = upgrade_analyzer or UpgradePathAnalyzer()

    @staticmethod
    def _normalize_project_type(project_type) -> ProjectType:
        if isinstance(project_type, ProjectType):
            return project_type
        try:
            return ProjectType(project_type)
        except ValueError:
            return ProjectType.UNKNOWN

    def select_workflow(
        self,
        project_type,
        source_version: str,
        target_version: str,
    ) -> Dict[str, Any]:
        ptype = self._normalize_project_type(project_type)
        steps: List[str] = list(_BASE_STEPS.get(ptype, _BASE_STEPS[ProjectType.OPEN_STUDIO]))

        hops = self.upgrade_analyzer.build_hops(source_version, target_version)
        if len(hops) > 1:
            steps.insert(len(steps) - 1, _INTERMEDIATE_HOP_STEP)

        if ptype == ProjectType.CLOUD or target_version == "Talend Cloud":
            steps.append(_CLOUD_FINAL_STEP)

        return {
            "projectType": ptype.value,
            "sourceVersion": source_version,
            "targetVersion": target_version,
            "hops": hops,
            "workflowId": f"{ptype.value.lower().replace(' ', '_')}_{len(hops)}hop",
            "steps": steps,
        }


def select_workflow(project_type, source_version: str, target_version: str) -> Dict[str, Any]:
    """Convenience wrapper around WorkflowSelector.select_workflow."""
    return WorkflowSelector().select_workflow(project_type, source_version, target_version)
