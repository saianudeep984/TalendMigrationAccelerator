from __future__ import annotations
from typing import Any, Dict
from app.config.component_rules import DEPRECATED_COMPONENT_MAP, TALEND8_KNOWN_COMPONENTS
from app.analyzers.version_upgrade_analyzer import UpgradePathAnalyzer
from .upgrade_inventory import components, ctype


class CompatibilityMatrixEngine:
    BREAKING = {"tSystem", "tMom", "tESBConsumer", "tRouteInput", "tRouteOutput", "tMDMInput", "tMDMOutput"}

    def build(self, source_version="Talend 7.x", target_version="Talend 8.x") -> Dict[str, Any]:
        path = UpgradePathAnalyzer().analyze_path(source_version, target_version)
        return {"source_version": source_version, "target_version": target_version, "path": path,
                "classifications": ["Compatible", "Warning", "Deprecated", "Unsupported", "Breaking Change"],
                "deprecated_components": DEPRECATED_COMPONENT_MAP, "known_talend8_components": sorted(TALEND8_KNOWN_COMPONENTS)}

    def classify_project(self, jobs, source_version="Talend 7.x", target_version="Talend 8.x") -> Dict[str, Any]:
        rows = []
        for j in jobs or []:
            name = (j.get("job_data") or j).get("job_name") or j.get("job_name")
            for c in components(j):
                t = ctype(c)
                if t in self.BREAKING:
                    status = "Breaking Change"
                elif t in DEPRECATED_COMPONENT_MAP:
                    status = "Deprecated"
                elif t not in TALEND8_KNOWN_COMPONENTS:
                    status = "Unsupported"
                elif t.startswith("tJava") or t in {"tBeanShell", "tGroovy", "tLibraryLoad"}:
                    status = "Warning"
                else:
                    status = "Compatible"
                rows.append({"job_name": name, "component": t, "status": status})
        counts = {s: sum(r["status"] == s for r in rows) for s in self.build()["classifications"]}
        return {"matrix": self.build(source_version, target_version), "findings": rows, "summary": counts}
