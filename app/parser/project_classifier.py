"""
project_classifier.py
Detects Talend project type (Open Studio / Enterprise / Cloud) from an
uploaded ZIP without fully extracting it.

Classification logic
--------------------
1. Cloud  — talend.project productVersion contains "Cloud" OR "TIAP" OR
             project root contains a cloud-marker file (e.g. .remote_project,
             manifest.yaml with a cloudProjectId key).
2. Enterprise — talend.project productVersion does NOT contain "Open Studio"
                and does NOT match Cloud signals, OR .project/.settings trees
                indicate a TAC-managed workspace (storageType="remote").
3. Open Studio — productVersion contains "Open Studio" (default fallback).

If talend.project is absent the classifier falls back to structural heuristics
(presence of .remote_project file → Cloud; presence of .settings folder only →
Enterprise; otherwise → Open Studio).

Public API
----------
    from app.parser.project_classifier import ProjectClassifier, ProjectType

    result = ProjectClassifier().classify_zip("/path/to/upload.zip")
    # result.project_type  → ProjectType.OPEN_STUDIO | ENTERPRISE | CLOUD
    # result.confidence    → "HIGH" | "MEDIUM" | "LOW"
    # result.version       → e.g. "Talend 7" or "UNKNOWN"
    # result.signals       → list[str] – human-readable reasons
    # result.to_dict()     → dict for JSON serialisation
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Constants ─────────────────────────────────────────────────────────────────

_RE_PRODUCT_VERSION = re.compile(
    r'productVersion\s*=\s*"([^"]+)"', re.IGNORECASE
)
_RE_STORAGE_TYPE = re.compile(
    r'storageType\s*=\s*"([^"]+)"', re.IGNORECASE
)
_RE_TALEND_VERSION = re.compile(r'\b([6-8])\.\d+')

# Files whose mere presence inside the ZIP signals a Cloud project
_CLOUD_MARKER_FILES = {
    ".remote_project",
    "manifest.yaml",
    "manifest.yml",
}

_CLOUD_KEYWORDS = frozenset(["cloud", "tiap", "talend cloud", "data fabric"])
_ENTERPRISE_KEYWORDS = frozenset(
    ["data integration", "data management", "mdm", "big data", "enterprise"]
)
_OPEN_STUDIO_KEYWORDS = frozenset(["open studio"])


# ── Domain types ──────────────────────────────────────────────────────────────

class ProjectType(str, Enum):
    OPEN_STUDIO = "Open Studio"
    ENTERPRISE  = "Enterprise"
    CLOUD       = "Cloud"
    UNKNOWN     = "Unknown"


@dataclass
class ClassificationResult:
    project_type: ProjectType = ProjectType.UNKNOWN
    confidence: str = "LOW"          # HIGH | MEDIUM | LOW
    version: str = "UNKNOWN"         # Talend 6 / 7 / 8 / UNKNOWN
    product_version_string: str = "" # raw productVersion attribute value
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_type": self.project_type.value,
            "confidence": self.confidence,
            "version": self.version,
            "product_version_string": self.product_version_string,
            "signals": self.signals,
        }


# ── Classifier ────────────────────────────────────────────────────────────────

class ProjectClassifier:
    """Classify a Talend project ZIP without fully extracting it."""

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def classify_zip(self, zip_path: str) -> ClassificationResult:
        """
        Parameters
        ----------
        zip_path : str
            Filesystem path to the uploaded ZIP archive.

        Returns
        -------
        ClassificationResult
        """
        result = ClassificationResult()
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                self._classify_from_names_and_content(zf, names, result)
        except zipfile.BadZipFile:
            result.signals.append("Invalid ZIP file — cannot classify.")
        return result

    def classify_extracted(self, repo_path: str) -> ClassificationResult:
        """
        Classify an already-extracted repository directory.

        Parameters
        ----------
        repo_path : str
            Root directory of the extracted Talend project.
        """
        import os

        result = ClassificationResult()
        # Walk to find talend.project
        for root, _dirs, files in os.walk(repo_path):
            for fname in files:
                if fname == "talend.project":
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read()
                        self._parse_talend_project(content, result)
                        if result.project_type != ProjectType.UNKNOWN:
                            return result
                    except OSError:
                        pass

        # Structural fallback
        file_set = set()
        for root, _dirs, files in os.walk(repo_path):
            for f in files:
                file_set.add(f.lower())
        self._structural_fallback(file_set, result)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_from_names_and_content(
        self,
        zf: zipfile.ZipFile,
        names: list[str],
        result: ClassificationResult,
    ) -> None:
        lower_names = [n.lower() for n in names]
        base_names  = {n.rsplit("/", 1)[-1].lower() for n in lower_names}

        # ── 1. Try talend.project (most reliable signal) ───────────────
        for name in names:
            if name.lower().endswith("talend.project"):
                try:
                    content = zf.read(name).decode("utf-8", errors="ignore")
                    self._parse_talend_project(content, result)
                    if result.project_type != ProjectType.UNKNOWN:
                        return
                except Exception:
                    result.signals.append(
                        f"Could not read {name} — falling back to structure."
                    )
                break  # only process first talend.project found

        # ── 2. Structural fallback ─────────────────────────────────────
        self._structural_fallback(base_names, result)

    def _parse_talend_project(
        self, content: str, result: ClassificationResult
    ) -> None:
        """Populate *result* from talend.project XML text."""

        # Extract version
        ver_match = _RE_TALEND_VERSION.search(content)
        if ver_match:
            major = ver_match.group(1)
            result.version = f"Talend {major}"

        # Extract productVersion attribute
        pv_match = _RE_PRODUCT_VERSION.search(content)
        if pv_match:
            pv = pv_match.group(1)
            result.product_version_string = pv
            pv_lower = pv.lower()

            if any(kw in pv_lower for kw in _CLOUD_KEYWORDS):
                result.project_type = ProjectType.CLOUD
                result.confidence    = "HIGH"
                result.signals.append(
                    f'productVersion "{pv}" matches Cloud keywords.'
                )
                return

            if any(kw in pv_lower for kw in _OPEN_STUDIO_KEYWORDS):
                result.project_type = ProjectType.OPEN_STUDIO
                result.confidence    = "HIGH"
                result.signals.append(
                    f'productVersion "{pv}" contains "Open Studio".'
                )
                return

            # Anything else with a Talend brand is most likely Enterprise
            if "talend" in pv_lower:
                result.project_type = ProjectType.ENTERPRISE
                result.confidence    = "MEDIUM"
                result.signals.append(
                    f'productVersion "{pv}" is a Talend product but not '
                    f'"Open Studio" or Cloud — classified as Enterprise.'
                )
                return

        # Check storageType
        st_match = _RE_STORAGE_TYPE.search(content)
        if st_match:
            storage = st_match.group(1).lower()
            if storage == "remote":
                result.project_type = ProjectType.ENTERPRISE
                result.confidence    = "MEDIUM"
                result.signals.append(
                    'storageType="remote" indicates TAC-managed Enterprise project.'
                )
                return
            if storage == "local":
                result.project_type = ProjectType.OPEN_STUDIO
                result.confidence    = "MEDIUM"
                result.signals.append(
                    'storageType="local" indicates Open Studio project.'
                )
                return

        result.signals.append(
            "talend.project found but no decisive product keyword detected."
        )

    def _structural_fallback(
        self, base_names: set[str], result: ClassificationResult
    ) -> None:
        """Use file-name heuristics when talend.project gives no answer."""

        if any(m in base_names for m in _CLOUD_MARKER_FILES):
            result.project_type = ProjectType.CLOUD
            result.confidence    = "MEDIUM"
            result.signals.append(
                f"Cloud marker file found ({_CLOUD_MARKER_FILES & base_names})."
            )
            return

        has_settings = any(
            n in base_names for n in {".project", "org.eclipse.core.resources.prefs"}
        )
        if has_settings:
            result.project_type = ProjectType.ENTERPRISE
            result.confidence    = "LOW"
            result.signals.append(
                "Eclipse .project/.settings structure suggests Enterprise workspace."
            )
            return

        if "talend.project" in base_names:
            # Present but unreadable earlier; default to Open Studio
            result.project_type = ProjectType.OPEN_STUDIO
            result.confidence    = "LOW"
            result.signals.append(
                "talend.project present but unreadable; defaulting to Open Studio."
            )
            return

        result.project_type = ProjectType.UNKNOWN
        result.confidence    = "LOW"
        result.signals.append(
            "No recognisable Talend project markers found in archive."
        )
