import os
import re
from typing import Any, Dict, Sequence

from app.tiap.models.repository import ROUTINE_SYSTEM_NAMES, iter_job_data, normalize_name, scan_repository_files


class RoutineProfiler:
    def profile(self, all_jobs: Sequence[Dict[str, Any]], repository_path: str = None) -> Dict[str, Any]:
        referenced = set()
        for data in iter_job_data(all_jobs):
            for component in data.get("components", []):
                if not isinstance(component, dict):
                    continue
                for value in (component.get("parameters") or {}).values():
                    referenced.update(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", str(value)))

        rows = []
        routine_files = scan_repository_files(repository_path).get("routines", []) if repository_path else []
        for path in routine_files:
            name = normalize_name(os.path.basename(path).replace(".item", ""))
            source_path = self._source_path(path, repository_path)
            source = self._read(source_path)
            rows.append(self._row(name, path, source, name in referenced))

        for name in sorted(referenced - {r["routine"] for r in rows}):
            rows.append(self._row(name, "", "", True))

        return {
            "routine_usage": rows,
            "custom_routines": [r for r in rows if r["is_custom"]],
            "java_usage": [r for r in rows if r["java_usage"]],
            "cloud_risks": [r for r in rows if r["cloud_risks"]],
            "risk_scores": {r["routine"]: r["risk_score"] for r in rows},
        }

    def _row(self, name: str, path: str, source: str, referenced: bool) -> Dict[str, Any]:
        is_custom = name not in ROUTINE_SYSTEM_NAMES and "\\system\\" not in path.lower() and "/system/" not in path.lower()
        flags = {
            "file_access": bool(re.search(r"\b(File|FileInputStream|FileOutputStream|Files\.|Path)\b", source)),
            "runtime_dependencies": bool(re.search(r"\bRuntime\.|ProcessBuilder|System\.load|ClassLoader\b", source)),
            "reflection_usage": bool(re.search(r"\bClass\.forName|getDeclared|java\.lang\.reflect\b", source)),
            "unsupported_apis": bool(re.search(r"\bsun\.|com\.sun\.|javax\.xml\.bind\b", source)),
        }
        score = (25 if is_custom else 5) + sum(20 for value in flags.values() if value)
        score = min(100, score)
        level = "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"
        return {
            "routine": name,
            "file_path": path,
            "referenced": referenced,
            "is_custom": is_custom,
            "java_usage": bool(source),
            **flags,
            "cloud_risks": [key for key, value in flags.items() if value],
            "risk_score": score,
            "risk": level,
        }

    def _source_path(self, item_path: str, repository_path: str) -> str:
        base = normalize_name(os.path.basename(item_path).replace(".item", ""))
        if not repository_path:
            return ""
        for path in scan_repository_files(repository_path).get("items", []):
            pass
        for root, _, files in os.walk(repository_path):
            for file in files:
                if file == f"{base}.java":
                    return os.path.join(root, file)
        return ""

    def _read(self, path: str) -> str:
        if not path or not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                return handle.read()
        except OSError:
            return ""


def profile_routines(all_jobs, repository_path=None):
    return RoutineProfiler().profile(all_jobs, repository_path)
