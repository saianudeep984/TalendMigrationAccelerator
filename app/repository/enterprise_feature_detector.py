"""
EnterpriseFeatureDetector

Scans a Talend repository (extracted path, ZIP bytes, or loaded repository
dict) for enterprise-only features and populates an EnterpriseFeatures dict:

    {
        "TAC":       { "detected": bool, "references": [...] },
        "JobServer": { "detected": bool, "references": [...] },
        "MDM":       { "detected": bool, "references": [...] },
        "DQ":        { "detected": bool, "references": [...] },
        "ESB":       { "detected": bool, "references": [...] },
        "summary":   ["TAC", "MDM", ...]   # list of detected features
    }
"""

import io
import os
import re
import zipfile
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Component-name prefix / pattern sets
# ---------------------------------------------------------------------------

TAC_COMPONENT_PREFIXES = (
    "tTACPublisher",
    "tTACService",
    "tTACInput",
    "tTACOutput",
    "tCommandLine",          # Used to invoke Talend CommandLine / TAC
)

TAC_PARAM_PATTERNS = [
    re.compile(r'\btac\b', re.IGNORECASE),
    re.compile(r'talend\s*administration\s*center', re.IGNORECASE),
    re.compile(r'commandline', re.IGNORECASE),
    re.compile(r'8080.*tac|tac.*8080', re.IGNORECASE),
]

JOBSERVER_COMPONENT_PREFIXES = (
    "tJobServerInput",
    "tJobServerOutput",
    "tJobInput",
    "tJobOutput",
    "tRemoteJobTrigger",
)

JOBSERVER_PARAM_PATTERNS = [
    re.compile(r'\bjob\s*server\b', re.IGNORECASE),
    re.compile(r'\bremote\s*job\b', re.IGNORECASE),
    re.compile(r'\bjobserver\b', re.IGNORECASE),
]

MDM_COMPONENT_PREFIXES = (
    "tMDM",
    "tMasterDataManagement",
)

MDM_PARAM_PATTERNS = [
    re.compile(r'\bmdm\b', re.IGNORECASE),
    re.compile(r'master\s*data\s*management', re.IGNORECASE),
    re.compile(r'talend\s*mdm', re.IGNORECASE),
]

DQ_COMPONENT_PREFIXES = (
    "tDQ",
    "tMatchGroup",
    "tSurvivorshipMerge",
    "tRecordMatching",
    "tDataQuality",
    "tStandardize",
    "tAddressRow",
)

DQ_PARAM_PATTERNS = [
    re.compile(r'\bdq\b', re.IGNORECASE),
    re.compile(r'data\s*quality', re.IGNORECASE),
    re.compile(r'tdq[_\-]', re.IGNORECASE),
    re.compile(r'\bTDQ_Libraries\b'),
]

ESB_COMPONENT_PREFIXES = (
    "tESB",
    "tRESTRequest",
    "tRESTResponse",
    "tSOAP11",
    "tSOAP12",
    "tServiceActivity",
    "tRouteInput",
    "tRouteOutput",
    "tCamel",
    "tSAM",
    "tSTS",
)

ESB_PARAM_PATTERNS = [
    re.compile(r'\besb\b', re.IGNORECASE),
    re.compile(r'enterprise\s*service\s*bus', re.IGNORECASE),
    re.compile(r'talend\s*esb', re.IGNORECASE),
    re.compile(r'\bcamel\b', re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# File-path signals for TAC / JobServer (in talend.project or .item paths)
# ---------------------------------------------------------------------------

TAC_PATH_PATTERNS = [
    re.compile(r'commandline', re.IGNORECASE),
    re.compile(r'/tac/', re.IGNORECASE),
]

JOBSERVER_PATH_PATTERNS = [
    re.compile(r'jobserver', re.IGNORECASE),
    re.compile(r'job.server', re.IGNORECASE),
]

MDM_PATH_PATTERNS = [
    re.compile(r'/mdm/', re.IGNORECASE),
    re.compile(r'masterdata', re.IGNORECASE),
]

DQ_PATH_PATTERNS = [
    re.compile(r'/TDQ', re.IGNORECASE),
    re.compile(r'dataquality', re.IGNORECASE),
]

ESB_PATH_PATTERNS = [
    re.compile(r'/esb/', re.IGNORECASE),
    re.compile(r'route[s]?/', re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _empty_feature() -> Dict[str, Any]:
    return {"detected": False, "references": []}


def _empty_features() -> Dict[str, Any]:
    return {
        "TAC": _empty_feature(),
        "JobServer": _empty_feature(),
        "MDM": _empty_feature(),
        "DQ": _empty_feature(),
        "ESB": _empty_feature(),
        "summary": [],
    }


def _add_ref(features: Dict, feature: str, ref: str) -> None:
    bucket = features[feature]
    bucket["detected"] = True
    if ref not in bucket["references"]:
        bucket["references"].append(ref)


def _check_component(
    features: Dict,
    component_type: str,
    source_label: str,
    parameters: Dict[str, str] = None,
) -> None:
    """Check a single component name (and optional parameters) against all feature sets."""
    ct = component_type or ""
    params_text = " ".join(str(v) for v in (parameters or {}).values())

    # TAC
    if ct.startswith(TAC_COMPONENT_PREFIXES) or any(
        p.search(params_text) for p in TAC_PARAM_PATTERNS
    ):
        _add_ref(features, "TAC", f"{source_label} [{ct}]")

    # JobServer
    if ct.startswith(JOBSERVER_COMPONENT_PREFIXES) or any(
        p.search(params_text) for p in JOBSERVER_PARAM_PATTERNS
    ):
        _add_ref(features, "JobServer", f"{source_label} [{ct}]")

    # MDM
    if ct.startswith(MDM_COMPONENT_PREFIXES) or any(
        p.search(params_text) for p in MDM_PARAM_PATTERNS
    ):
        _add_ref(features, "MDM", f"{source_label} [{ct}]")

    # DQ
    if ct.startswith(DQ_COMPONENT_PREFIXES) or any(
        p.search(params_text) for p in DQ_PARAM_PATTERNS
    ):
        _add_ref(features, "DQ", f"{source_label} [{ct}]")

    # ESB
    if ct.startswith(ESB_COMPONENT_PREFIXES) or any(
        p.search(params_text) for p in ESB_PARAM_PATTERNS
    ):
        _add_ref(features, "ESB", f"{source_label} [{ct}]")


def _check_file_path(features: Dict, path: str) -> None:
    """Check a file path for enterprise feature signals."""
    for pattern in TAC_PATH_PATTERNS:
        if pattern.search(path):
            _add_ref(features, "TAC", f"path: {path}")
    for pattern in JOBSERVER_PATH_PATTERNS:
        if pattern.search(path):
            _add_ref(features, "JobServer", f"path: {path}")
    for pattern in MDM_PATH_PATTERNS:
        if pattern.search(path):
            _add_ref(features, "MDM", f"path: {path}")
    for pattern in DQ_PATH_PATTERNS:
        if pattern.search(path):
            _add_ref(features, "DQ", f"path: {path}")
    for pattern in ESB_PATH_PATTERNS:
        if pattern.search(path):
            _add_ref(features, "ESB", f"path: {path}")


def _check_xml_content(features: Dict, content_str: str, source_label: str) -> None:
    """
    Fast regex scan of raw .item XML content to catch component names and
    parameter values without a full XML parse.
    """
    # Extract componentName attributes
    for m in re.finditer(r'componentName=["\']([^"\']+)["\']', content_str):
        ct = m.group(1)
        _check_component(features, ct, source_label)

    # Scan full content for patterns that may appear in parameter values
    _check_content_text(features, content_str, source_label)


def _check_content_text(features: Dict, text: str, source_label: str) -> None:
    """Scan raw text (talend.project, .item, etc.) for enterprise feature signals."""
    for p in TAC_PARAM_PATTERNS:
        if p.search(text):
            _add_ref(features, "TAC", f"content match in {source_label}")
            break
    for p in JOBSERVER_PARAM_PATTERNS:
        if p.search(text):
            _add_ref(features, "JobServer", f"content match in {source_label}")
            break
    for p in MDM_PARAM_PATTERNS:
        if p.search(text):
            _add_ref(features, "MDM", f"content match in {source_label}")
            break
    for p in DQ_PARAM_PATTERNS:
        if p.search(text):
            _add_ref(features, "DQ", f"content match in {source_label}")
            break
    for p in ESB_PARAM_PATTERNS:
        if p.search(text):
            _add_ref(features, "ESB", f"content match in {source_label}")
            break


def _finalise(features: Dict) -> Dict:
    """Populate summary list."""
    features["summary"] = [
        k for k in ("TAC", "JobServer", "MDM", "DQ", "ESB")
        if features[k]["detected"]
    ]
    return features


# ---------------------------------------------------------------------------
# Public service
# ---------------------------------------------------------------------------

class EnterpriseFeatureDetector:
    """
    Detect enterprise feature usage in a Talend repository and populate
    EnterpriseFeatures.

    Usage
    -----
    detector = EnterpriseFeatureDetector()

    # From extracted directory
    result = detector.detect_from_path("/path/to/repo")

    # From raw ZIP bytes (e.g. st.session_state uploaded bytes)
    result = detector.detect_from_zip_bytes(zip_bytes)

    # From already-loaded repository dict (RepositoryLoader output)
    result = detector.detect_from_repository(repository)

    # From parsed job list (all_jobs from analysis pipeline)
    result = detector.detect_from_jobs(all_jobs)

    Each returns an EnterpriseFeatures dict:
    {
        "TAC":       {"detected": True/False, "references": [...]},
        "JobServer": {"detected": True/False, "references": [...]},
        "MDM":       {"detected": True/False, "references": [...]},
        "DQ":        {"detected": True/False, "references": [...]},
        "ESB":       {"detected": True/False, "references": [...]},
        "summary":   ["TAC", "MDM", ...]
    }
    """

    # ------------------------------------------------------------------
    # detect_from_path
    # ------------------------------------------------------------------

    def detect_from_path(self, repository_path: str) -> Dict[str, Any]:
        """Scan an extracted repository directory for enterprise features."""
        features = _empty_features()

        for root, dirs, files in os.walk(repository_path):
            for file_name in files:
                full_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(full_path, repository_path)

                _check_file_path(features, rel_path)

                if file_name.endswith(".item") or file_name == "talend.project":
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read()
                        _check_xml_content(features, content, rel_path)
                    except Exception:
                        pass

        return _finalise(features)

    # ------------------------------------------------------------------
    # detect_from_zip_bytes
    # ------------------------------------------------------------------

    def detect_from_zip_bytes(self, zip_bytes: bytes) -> Dict[str, Any]:
        """Scan a raw ZIP for enterprise features."""
        features = _empty_features()

        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except Exception:
            return _finalise(features)

        for name in zf.namelist():
            _check_file_path(features, name)

            low = name.lower()
            if low.endswith(".item") or low.endswith("talend.project"):
                try:
                    content = zf.read(name).decode("utf-8", errors="ignore")
                    _check_xml_content(features, content, name)
                except Exception:
                    pass

        return _finalise(features)

    # ------------------------------------------------------------------
    # detect_from_repository
    # ------------------------------------------------------------------

    def detect_from_repository(self, repository: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scan a loaded repository dict (from RepositoryLoader.load_repository)
        for enterprise features.
        """
        features = _empty_features()

        for bucket_key in ("items", "properties", "other_files"):
            for entry in repository.get(bucket_key, []):
                path = entry.get("path", "")
                _check_file_path(features, path)

                low = path.lower()
                if low.endswith(".item") or low.endswith("talend.project"):
                    try:
                        content = entry["content"].decode("utf-8", errors="ignore")
                        _check_xml_content(features, content, path)
                    except Exception:
                        pass

        return _finalise(features)

    # ------------------------------------------------------------------
    # detect_from_jobs
    # ------------------------------------------------------------------

    def detect_from_jobs(self, all_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Scan parsed job list (the all_jobs list from the analysis pipeline,
        each entry having a 'job_data' key) for enterprise features.
        """
        features = _empty_features()

        for job_entry in all_jobs:
            job_data = job_entry.get("job_data", job_entry)
            job_name = job_data.get("job_name", "unknown")
            file_path = job_entry.get("file_path", "")

            if file_path:
                _check_file_path(features, file_path)

            for component in job_data.get("components", []):
                if not isinstance(component, dict):
                    continue
                ct = component.get("component_type", "")
                params = {
                    k: v for k, v in component.get("parameters", {}).items()
                    if v
                }
                _check_component(features, ct, job_name, params)

        return _finalise(features)
