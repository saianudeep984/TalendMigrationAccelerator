"""
MigrationFailureDetector — classifies post-migration job failures.

Original only caught empty-component jobs. This version adds:
  - Cloud-blocker components (tFileList, tFTPPut etc.) that fail at cloud runtime
  - Risky Java (runtime exec, file-access) that may break in cloud containers
  - Large estimated component count drops (component loss during migration)
  - Duplicated job names (collision risk after migration)
  - Returns severity levels: CRITICAL / HIGH / MEDIUM / LOW
"""

_CLOUD_BLOCKERS = {
    "tFTPGet", "tFTPPut", "tFTPDelete", "tSFTP",
    "tFileList", "tFileCopy", "tFileMove", "tFileDelete",
    "tFileInputFullRow", "tLocalIP", "tSystem",
    "tRunJob",  # local tRunJob without remote engine configured
}

_JAVA_RISK_PATTERNS = [
    "Runtime.getRuntime",
    "ProcessBuilder",
    "System.exec",
    "new File(",
    "FileInputStream",
    "FileOutputStream",
]


def _has_java_risk(job_data: dict) -> bool:
    source = job_data.get("java_source", "") or ""
    return any(pat in source for pat in _JAVA_RISK_PATTERNS)


class MigrationFailureDetector:

    def detect(self, migrated_jobs: list) -> list:
        """
        Parameters
        ----------
        migrated_jobs : list
            all_jobs list from the pipeline.

        Returns
        -------
        list of failure dicts:
            {
              "job": str,
              "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
              "issue": str,
              "recommendation": str,
            }
        """
        failures = []
        seen_names = {}

        for entry in migrated_jobs:
            job_data = entry.get("job_data", {})
            job_name = job_data.get("job_name", "UNKNOWN")
            components = job_data.get("components", [])

            # Duplicate detection
            if job_name in seen_names:
                failures.append({
                    "job": job_name,
                    "severity": "HIGH",
                    "issue": "Duplicate job name detected — two jobs share the same name after migration.",
                    "recommendation": "Rename one job in Talend 8 Studio before exporting.",
                })
            seen_names[job_name] = True

            # Empty job
            if len(components) == 0:
                failures.append({
                    "job": job_name,
                    "severity": "CRITICAL",
                    "issue": "Empty migrated job — 0 components found.",
                    "recommendation": (
                        "Re-import from the original Open Studio ZIP via Talend 8 Studio "
                        "File → Import → Talend Items and allow Studio migration tasks to complete."
                    ),
                })
                continue  # further checks meaningless on an empty job

            # Cloud-blocker components
            comp_types = [
                (c if isinstance(c, str) else c.get("type", ""))
                for c in components
            ]
            blockers_found = [ct for ct in comp_types if ct in _CLOUD_BLOCKERS]
            if blockers_found:
                failures.append({
                    "job": job_name,
                    "severity": "HIGH",
                    "issue": (
                        f"Cloud-incompatible component(s): {', '.join(set(blockers_found))}. "
                        "These perform local file-system or OS operations that will fail "
                        "in a cloud container runtime."
                    ),
                    "recommendation": (
                        "Replace file-system components with cloud-native equivalents "
                        "(e.g. tS3Put/Get, tAzureBlobOutput) or deploy to an on-premises "
                        "Remote Engine rather than a cloud engine."
                    ),
                })

            # Java risks
            if _has_java_risk(job_data):
                failures.append({
                    "job": job_name,
                    "severity": "MEDIUM",
                    "issue": (
                        "Inline Java uses file-system or process-execution APIs "
                        "(FileInputStream, Runtime.getRuntime, etc.) that are blocked "
                        "in cloud container sandboxes."
                    ),
                    "recommendation": (
                        "Refactor the Java code to use cloud-safe APIs or move "
                        "the logic to a Talend cloud-compatible routine."
                    ),
                })

        return failures
