from typing import Dict, List, Any


class RiskAnalyzer:

    def analyze(
        self,
        job_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Analyze migration risks based on Talend components.

        Each element in job_data["components"] is a dict:
            { "component_type": str, "unique_name": str, "parameters": dict }

        Args:
            job_data (Dict): Parsed Talend job data

        Returns:
            List[Dict]: List of identified risks (deduplicated by component type)
        """

        risks = []
        seen_types: set = set()

        components = job_data.get("components", [])

        for component in components:

            # components are dicts — extract the type string
            comp_type = component.get("component_type", "") if isinstance(component, dict) else str(component)

            # Deduplicate: only report each component type once per job
            if comp_type in seen_types:
                continue
            seen_types.add(comp_type)

            # tJava / tJavaRow / tJavaFlex risk
            if comp_type in ("tJava", "tJavaRow", "tJavaFlex"):
                risks.append({
                    "component": comp_type,
                    "risk": "HIGH",
                    "reason": "Custom Java code detected",
                    "recommendation": (
                        "Refactor logic using Talend native components "
                        "or reusable routines"
                    )
                })

            # tSystem risk
            elif comp_type == "tSystem":
                risks.append({
                    "component": comp_type,
                    "risk": "CRITICAL",
                    "reason": "OS-level command execution — not cloud-safe",
                    "recommendation": (
                        "Replace with a cloud function, REST call, "
                        "or Talend Cloud-native equivalent"
                    )
                })

            # tLibraryLoad risk
            elif comp_type == "tLibraryLoad":
                risks.append({
                    "component": comp_type,
                    "risk": "HIGH",
                    "reason": "External JAR library dependency",
                    "recommendation": (
                        "Validate library availability in the cloud runtime "
                        "or bundle it as a shared resource"
                    )
                })

            # tBeanShell risk
            elif comp_type == "tBeanShell":
                risks.append({
                    "component": comp_type,
                    "risk": "HIGH",
                    "reason": "Deprecated scripting component",
                    "recommendation": "Rewrite logic in tJavaRow"
                })

            # tRunJob risk
            elif comp_type == "tRunJob":
                risks.append({
                    "component": comp_type,
                    "risk": "MEDIUM",
                    "reason": "Child job dependency — orchestration must be validated",
                    "recommendation": (
                        "Validate orchestration chain migrates correctly; "
                        "consider Talend Cloud Pipelines or Jobs-as-Services"
                    )
                })

            # Oracle CDC risk
            elif comp_type == "tOracleCDC":
                risks.append({
                    "component": comp_type,
                    "risk": "MEDIUM",
                    "reason": "CDC migration complexity detected",
                    "recommendation": (
                        "Use Talend Cloud CDC framework "
                        "or redesign incremental processing"
                    )
                })

            # tMap — low risk, validation required
            elif comp_type in ("tMap", "tXMLMap"):
                risks.append({
                    "component": comp_type,
                    "risk": "LOW",
                    "reason": "Complex mapping — output must be validated after migration",
                    "recommendation": "Validate field mappings and expressions in Talend 8 Studio"
                })

        return risks
