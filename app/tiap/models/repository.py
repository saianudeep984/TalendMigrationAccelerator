import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from lxml import etree as ET

from app.parser.talend_xml_parser import TalendJobParser
from app.cache.cache_manager import CacheManager as _CacheManager

_tma_cache = _CacheManager()


def load_jobs_from_repository(repository_path: str) -> List[Dict[str, Any]]:
    jobs = []
    for path in scan_repository_files(repository_path)["jobs"]:
        data = _tma_cache.load_or_parse(path)
        if data.get("job_name") != "INVALID_JOB":
            data["file_path"] = path
            jobs.append({"job_data": data})
    return jobs



ROUTINE_SYSTEM_NAMES = {
    "DataOperation",
    "Mathematical",
    "Numeric",
    "Relational",
    "StringHandling",
    "TalendDataGenerator",
    "TalendDate",
    "TalendString",
}


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().strip('"').strip("'")
    text = text.replace(".item", "")
    text = re.sub(r"_\d+\.\d+$", "", text)
    return text


def extract_job_data(job: Dict[str, Any]) -> Dict[str, Any]:
    if "job_data" in job and isinstance(job["job_data"], dict):
        return job["job_data"]
    return job


def iter_job_data(all_jobs: Sequence[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for job in all_jobs or []:
        data = extract_job_data(job)
        if isinstance(data, dict):
            yield data


def safe_ratio_score(good: float, total: float) -> int:
    if total <= 0:
        return 100
    return max(0, min(100, int(round((good / total) * 100))))


def risk_level(score: int) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: str, payload: Dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4, default=str)
    return path


def parse_xml(path: str) -> Optional[ET._Element]:
    try:
        parser = ET.XMLParser(recover=True, encoding="utf-8", huge_tree=True)
        return ET.parse(path, parser).getroot()
    except Exception:
        return None


def local_name(tag: Any) -> str:
    text = str(tag or "")
    if "}" in text:
        return text.split("}", 1)[1]
    return text


def iter_elements(root: Optional[ET._Element], name: Optional[str] = None):
    if root is None:
        return
    for elem in root.iter():
        if name is None or local_name(elem.tag) == name:
            yield elem


def scan_repository_files(repository_path: str) -> Dict[str, List[str]]:
    root = Path(repository_path)
    files = {
        "jobs": [],
        "joblets": [],
        "contexts": [],
        "routines": [],
        "metadata": [],
        "items": [],
    }
    if not root.exists():
        return files
    for item in root.rglob("*.item"):
        path = str(item)
        low = path.lower().replace("\\", "/")
        files["items"].append(path)
        if "/process/" in low:
            files["jobs"].append(path)
        elif "/joblets/" in low or "/joblet/" in low:
            files["joblets"].append(path)
        elif "/context/" in low or "/contexts/" in low:
            files["contexts"].append(path)
        elif "/code/routines/" in low:
            files["routines"].append(path)
        elif "/metadata/" in low:
            files["metadata"].append(path)
    return files


def get_component_names(all_jobs: Sequence[Dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for data in iter_job_data(all_jobs):
        for component in data.get("components", []):
            ctype = component.get("component_type") if isinstance(component, dict) else str(component)
            if ctype:
                counter[ctype] += 1
    return counter


def component_parameters(component: Dict[str, Any]) -> Dict[str, str]:
    params = dict(component.get("parameters", {}) or {})
    for key, value in component.items():
        if key not in ("parameters", "component_type", "unique_name") and value:
            params.setdefault(key.upper(), value)
    return {str(k): str(v) for k, v in params.items() if v is not None}


def extract_referenced_names(text: str, candidates: Iterable[str]) -> Set[str]:
    found: Set[str] = set()
    haystack = str(text or "")
    for candidate in candidates:
        if candidate and re.search(rf"\b{re.escape(candidate)}\b", haystack):
            found.add(candidate)
    return found


def inventory_reference_sets(all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Set[str]]:
    refs = {
        "contexts": set(),
        "joblets": set(),
        "routines": set(),
        "metadata": set(),
    }
    for data in iter_job_data(all_jobs):
        for context in data.get("contexts", []):
            if isinstance(context, dict) and context.get("name"):
                refs["contexts"].add(str(context["name"]))
        for component in data.get("components", []):
            if not isinstance(component, dict):
                continue
            ctype = component.get("component_type", "")
            params = component_parameters(component)
            if ctype.lower().startswith("tjoblet") or ctype == "tJoblet":
                refs["joblets"].add(params.get("JOBLET") or params.get("PROCESS") or component.get("unique_name") or ctype)
            for value in params.values():
                value_text = str(value)
                if "context." in value_text:
                    refs["contexts"].update(re.findall(r"context\.([A-Za-z_][A-Za-z0-9_]*)", value_text))
                refs["routines"].update(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", value_text))
                if "metadata" in value_text.lower() or "repository" in value_text.lower():
                    refs["metadata"].add(normalize_name(value_text.split("/")[-1]))
    return refs


def build_adjacency_from_jobs(all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Set[str]]:
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    for data in iter_job_data(all_jobs):
        parent = normalize_name(data.get("job_name", "Unknown"))
        adjacency.setdefault(parent, set())
        for component in data.get("components", []):
            if not isinstance(component, dict) or component.get("component_type") != "tRunJob":
                continue
            params = component_parameters(component)
            child = (
                params.get("PROCESS")
                or params.get("JOB_NAME")
                or params.get("CHILD_JOB")
                or params.get("PROCESS_NAME")
                or params.get("SUBPROCESS")
            )
            child = normalize_name(child)
            if child:
                adjacency[parent].add(child)
    return adjacency
