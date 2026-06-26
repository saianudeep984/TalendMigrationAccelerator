import re
from typing import Any, Dict, Sequence


class JavaRefactor:
    PATTERNS = {
        "file_operations": r"\b(File|FileInputStream|FileOutputStream|Files\.|BufferedReader|PrintWriter)\b",
        "jdbc_calls": r"\bDriverManager|Connection|PreparedStatement|ResultSet\b",
        "string_manipulation": r"\bStringBuilder|StringBuffer|substring|replaceAll|split\(",
        "loops": r"\b(for|while)\s*\(",
        "error_handling": r"\btry\s*\{|catch\s*\(",
    }

    def analyze(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        rows = []
        for job in all_jobs:
            job_name = job.get("job_data", {}).get("job_name", "Unknown")
            for component in job.get("job_data", {}).get("components", []):
                ctype = component.get("component_type", "")
                if ctype not in {"tJava", "tJavaRow", "tJavaFlex"}:
                    continue
                text = " ".join(str(v) for v in (component.get("parameters") or {}).values())
                findings = {name: bool(re.search(pattern, text)) for name, pattern in self.PATTERNS.items()}
                rows.append({
                    "job": job_name,
                    "component": component.get("unique_name") or ctype,
                    "component_type": ctype,
                    **findings,
                    "suggested_components": self._suggest(findings),
                    "standardized_patterns": self._patterns(findings),
                })
        return {"tjava_analysis": rows, "java_modernization_suggestions": rows}

    def _suggest(self, findings):
        suggestions = []
        if findings.get("file_operations"):
            suggestions.extend(["tFileInputDelimited", "tFileOutputDelimited", "tFileList"])
        if findings.get("jdbc_calls"):
            suggestions.extend(["tDBInput", "tDBOutput", "tDBRow"])
        if findings.get("string_manipulation") or findings.get("loops"):
            suggestions.append("tMap")
        if findings.get("error_handling"):
            suggestions.extend(["tLogCatcher", "tDie", "tWarn"])
        return sorted(set(suggestions)) or ["Review for standard Talend component replacement"]

    def _patterns(self, findings):
        patterns = []
        if findings.get("jdbc_calls"):
            patterns.append("Repository DB connection with shared commit/close handling")
        if findings.get("string_manipulation"):
            patterns.append("tMap expression with reusable routines")
        if findings.get("file_operations"):
            patterns.append("Talend file component with context-driven paths")
        return patterns or ["No specific modernization pattern detected"]
