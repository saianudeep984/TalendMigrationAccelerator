from __future__ import annotations
from .compatibility_matrix import CompatibilityMatrixEngine


class BreakingChangeAnalyzer:
    def analyze(self, jobs, source_version="Talend 7.x", target_version="Talend 8.x"):
        classified = CompatibilityMatrixEngine().classify_project(jobs, source_version, target_version)
        breaking_status = {"Breaking Change", "Unsupported", "Deprecated"}
        findings = []
        for row in classified["findings"]:
            if row["status"] in breaking_status:
                sev = "CRITICAL" if row["status"] == "Breaking Change" else ("HIGH" if row["status"] == "Unsupported" else "MEDIUM")
                findings.append({"severity": sev, "category": row["status"], "root_cause": f"{row['component']} is {row['status'].lower()} for target runtime.",
                                 "affected_jobs": [row["job_name"]], "affected_assets": [row["component"]],
                                 "upgrade_guidance": "Replace, refactor, or validate with the target Talend 8 runtime."})
        return {"summary": {"total": len(findings), "critical": sum(f["severity"] == "CRITICAL" for f in findings)}, "findings": findings}
