from app.config.version_compatibility import VERSION_COMPATIBILITY
from app.config.version_matrix import VERSION_UPGRADE_MATRIX


class UpgradePathAnalyzer:
    """Determines the hop-by-hop upgrade path between two Talend versions
    and aggregates the renamed/removed components and parameter changes
    that apply along that path.
    """

    def __init__(self, version_matrix=None, compatibility_rules=None):

        self.version_matrix = (
            version_matrix
            if version_matrix is not None
            else VERSION_UPGRADE_MATRIX
        )

        self.compatibility_rules = (
            compatibility_rules
            if compatibility_rules is not None
            else VERSION_COMPATIBILITY
        )

    @staticmethod
    def _parse_major_version(version_label):

        digits = "".join(
            ch for ch in str(version_label) if ch.isdigit()
        )

        return int(digits) if digits else None

    def build_hops(self, source_version, target_version):

        source_major = self._parse_major_version(source_version)
        target_major = self._parse_major_version(target_version)

        if source_major is None or target_major is None:
            return []

        if source_major >= target_major:
            return []

        return [
            f"{major}_to_{major + 1}"
            for major in range(source_major, target_major)
        ]

    def analyze_path(self, source_version, target_version):

        hops = self.build_hops(source_version, target_version)

        path_report = {
            "sourceVersion": source_version,
            "targetVersion": target_version,
            "hops": hops,
            "supported": bool(hops),
            "renamedComponents": {},
            "removedComponents": [],
            "parameterChanges": {},
            "newRequiredParameters": {},
        }

        for hop in hops:

            hop_rules = self.version_matrix.get(hop, {})

            path_report["renamedComponents"].update(
                hop_rules.get("renamed_components", {})
            )

            for comp in hop_rules.get("removed_components", []):
                if comp not in path_report["removedComponents"]:
                    path_report["removedComponents"].append(comp)

            path_report["parameterChanges"].update(
                hop_rules.get("parameter_changes", {})
            )

            path_report["newRequiredParameters"].update(
                hop_rules.get("new_required_parameters", {})
            )

        return path_report

    def analyze_job(self, job_data, source_version, target_version):

        path_report = self.analyze_path(source_version, target_version)

        renamed = path_report["renamedComponents"]
        removed = set(path_report["removedComponents"])

        deprecated = self.compatibility_rules.get(
            source_version, {}
        ).get("deprecated_components", [])

        unsupported = self.compatibility_rules.get(
            source_version, {}
        ).get("unsupported_components", [])

        findings = []
        warnings = []

        for component in job_data.get("components", []):

            comp = component.get("component_type")

            if comp in removed:
                findings.append({
                    "component": comp,
                    "impact": "REMOVED",
                    "action": "Manual remediation required",
                })
            elif comp in renamed:
                findings.append({
                    "component": comp,
                    "impact": "RENAMED",
                    "action": f"Rename to {renamed[comp]}",
                })
            elif comp in unsupported:
                findings.append({
                    "component": comp,
                    "impact": "UNSUPPORTED",
                    "action": "Manual remediation required",
                })
            elif comp in deprecated:
                findings.append({
                    "component": comp,
                    "impact": "DEPRECATED",
                    "action": "Replace component",
                })

            if comp in deprecated:
                warnings.append({
                    "component": comp,
                    "category": "DEPRECATED",
                    "message": f"{comp} is deprecated in {source_version} and should be replaced before upgrading.",
                    "severity": "MEDIUM",
                })

            if comp in unsupported:
                warnings.append({
                    "component": comp,
                    "category": "UNSUPPORTED",
                    "message": f"{comp} is unsupported in {source_version} and requires manual remediation.",
                    "severity": "HIGH",
                })

        blockers = []

        if not path_report["supported"]:
            blockers.append(
                f"No supported upgrade path exists from {source_version} to {target_version}."
            )

        path_report["componentFindings"] = findings
        path_report["warnings"] = warnings
        path_report["blockers"] = blockers

        return path_report


def analyze_upgrade_impact(
    job_data,
    source_version,
    target_version
):

    report = []

    rules = VERSION_COMPATIBILITY.get(
        source_version,
        {}
    )

    deprecated = rules.get(
        "deprecated_components",
        []
    )

    unsupported = rules.get(
        "unsupported_components",
        []
    )

    for component in job_data["components"]:

        comp = component["component_type"]

        if comp in deprecated:

            report.append({

                "component": comp,

                "impact": "DEPRECATED",

                "action":
                "Replace component"
            })

        if comp in unsupported:

            report.append({

                "component": comp,

                "impact": "UNSUPPORTED",

                "action":
                "Manual remediation required"
            })

    return report