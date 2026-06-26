import os
import re
import zipfile
import io


OPEN_STUDIO_KEYWORDS = [
    "open studio",
    "tos",
    "talend open studio",
]

ENTERPRISE_KEYWORDS = [
    "talend data fabric",
    "talend data management",
    "talend data services",
    "talend integration cloud",
    "talend enterprise",
    "tdi",
    "tds",
    "tic",
    "tdf",
    "talend platform",
]

REPOSITORY_TYPE_OPEN_STUDIO = "Open Studio"
REPOSITORY_TYPE_ENTERPRISE = "Enterprise"
REPOSITORY_TYPE_UNKNOWN = "Unknown"


class RepositoryTypeDetector:

    # ------------------------------------------------------------------
    # Source Version Extraction
    # ------------------------------------------------------------------

    def extract_source_version_from_path(self, repository_path: str) -> str:
        """
        Extract the Talend source version string from talend.project in
        an extracted repository directory.
        Returns a version string like '7.3.1' or 'UNKNOWN'.
        """
        for root, dirs, files in os.walk(repository_path):
            for file in files:
                if file == "talend.project":
                    project_path = os.path.join(root, file)
                    try:
                        with open(project_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        return self._extract_source_version(content)
                    except Exception:
                        pass
        return "UNKNOWN"

    def extract_source_version_from_zip_bytes(self, zip_bytes: bytes) -> str:
        """
        Extract the Talend source version string from talend.project inside
        a raw ZIP.
        Returns a version string like '7.3.1' or 'UNKNOWN'.
        """
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except Exception:
            return "UNKNOWN"
        for name in zip_file.namelist():
            if name.endswith("talend.project"):
                try:
                    content = zip_file.read(name).decode("utf-8", errors="ignore")
                    return self._extract_source_version(content)
                except Exception:
                    pass
        return "UNKNOWN"

    def extract_source_version_from_repository(self, repository: dict) -> str:
        """
        Extract the Talend source version string from a loaded repository dict
        (as returned by RepositoryLoader.load_repository).
        Returns a version string like '7.3.1' or 'UNKNOWN'.
        """
        for file_entry in repository.get("other_files", []):
            path = file_entry.get("path", "")
            if path.endswith("talend.project"):
                try:
                    content = file_entry["content"].decode("utf-8", errors="ignore")
                    return self._extract_source_version(content)
                except Exception:
                    pass
        return "UNKNOWN"

    def _extract_source_version(self, content: str) -> str:
        """
        Extract the Talend source version from talend.project file content.

        Priority:
        1. productVersion attribute  e.g. Talend Open Studio for DI-7.3.1.20210901
        2. technicalLabel attribute  e.g. 7.3.1
        3. Any semver-like token (major 5-9) in the file
        """
        # 1. productVersion — extract trailing semver segment
        m = re.search(r'productVersion=["\']([^"\']+)["\']', content)
        if m:
            raw = m.group(1)
            ver = re.search(r'(\d+\.\d+\.\d+)', raw)
            if ver:
                return ver.group(1)
            # Fallback: major.minor only
            ver = re.search(r'(\d+\.\d+)', raw)
            if ver:
                return ver.group(1)

        # 2. technicalLabel
        m = re.search(r'technicalLabel=["\']([^"\']+)["\']', content)
        if m:
            raw = m.group(1)
            ver = re.search(r'(\d+\.\d+\.\d+)', raw)
            if ver:
                return ver.group(1)

        # 3. Any semver with major 5-9
        ver = re.search(r'\b([5-9]\.\d+\.\d+)\b', content)
        if ver:
            return ver.group(1)

        return "UNKNOWN"

    # ------------------------------------------------------------------
    # Combined detect (type + source_version in one call)
    # ------------------------------------------------------------------

    def detect_from_path(self, repository_path: str) -> dict:
        """
        Detect repository type from an extracted repository directory.
        Returns a dict with 'type', 'confidence', 'evidence', and 'source_version'.
        """
        for root, dirs, files in os.walk(repository_path):
            for file in files:
                if file == "talend.project":
                    project_path = os.path.join(root, file)
                    try:
                        with open(project_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        result = self._detect_from_content(content)
                        result["source_version"] = self._extract_source_version(content)
                        return result
                    except Exception:
                        pass

        return {
            "type": REPOSITORY_TYPE_UNKNOWN,
            "confidence": "low",
            "evidence": "No talend.project file found",
            "source_version": "UNKNOWN",
        }

    def detect_from_zip_bytes(self, zip_bytes: bytes) -> dict:
        """
        Detect repository type from raw ZIP bytes.
        Returns a dict with 'type', 'confidence', 'evidence', and 'source_version'.
        """
        try:
            zip_file = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except Exception:
            return {
                "type": REPOSITORY_TYPE_UNKNOWN,
                "confidence": "low",
                "evidence": "Could not open ZIP file",
                "source_version": "UNKNOWN",
            }

        for name in zip_file.namelist():
            if name.endswith("talend.project"):
                try:
                    content = zip_file.read(name).decode("utf-8", errors="ignore")
                    result = self._detect_from_content(content)
                    result["source_version"] = self._extract_source_version(content)
                    return result
                except Exception:
                    pass

        return {
            "type": REPOSITORY_TYPE_UNKNOWN,
            "confidence": "low",
            "evidence": "No talend.project file found in ZIP",
            "source_version": "UNKNOWN",
        }

    def detect_from_repository(self, repository: dict) -> dict:
        """
        Detect repository type from a loaded repository dict
        (as returned by RepositoryLoader.load_repository).
        Returns a dict with 'type', 'confidence', 'evidence', and 'source_version'.
        """
        for file_entry in repository.get("other_files", []):
            path = file_entry.get("path", "")
            if path.endswith("talend.project"):
                try:
                    content = file_entry["content"].decode("utf-8", errors="ignore")
                    result = self._detect_from_content(content)
                    result["source_version"] = self._extract_source_version(content)
                    return result
                except Exception:
                    pass

        return {
            "type": REPOSITORY_TYPE_UNKNOWN,
            "confidence": "low",
            "evidence": "No talend.project file found in repository",
            "source_version": "UNKNOWN",
        }

    def _detect_from_content(self, content: str) -> dict:
        """
        Detect repository type from talend.project file content.
        """
        product_version_raw = ""
        m = re.search(r'productVersion=["\']([^"\']+)["\']', content)
        if m:
            product_version_raw = m.group(1)

        product_lower = product_version_raw.lower()

        for keyword in ENTERPRISE_KEYWORDS:
            if keyword in product_lower:
                return {
                    "type": REPOSITORY_TYPE_ENTERPRISE,
                    "confidence": "high",
                    "evidence": f"productVersion: {product_version_raw}"
                }

        for keyword in OPEN_STUDIO_KEYWORDS:
            if keyword in product_lower:
                return {
                    "type": REPOSITORY_TYPE_OPEN_STUDIO,
                    "confidence": "high",
                    "evidence": f"productVersion: {product_version_raw}"
                }

        # Fallback: scan broader content for product signals
        content_lower = content.lower()

        for keyword in ENTERPRISE_KEYWORDS:
            if keyword in content_lower:
                return {
                    "type": REPOSITORY_TYPE_ENTERPRISE,
                    "confidence": "medium",
                    "evidence": f"Keyword '{keyword}' found in talend.project"
                }

        for keyword in OPEN_STUDIO_KEYWORDS:
            if keyword in content_lower:
                return {
                    "type": REPOSITORY_TYPE_OPEN_STUDIO,
                    "confidence": "medium",
                    "evidence": f"Keyword '{keyword}' found in talend.project"
                }

        if product_version_raw:
            return {
                "type": REPOSITORY_TYPE_UNKNOWN,
                "confidence": "low",
                "evidence": f"Unrecognised productVersion: {product_version_raw}"
            }

        return {
            "type": REPOSITORY_TYPE_UNKNOWN,
            "confidence": "low",
            "evidence": "No recognisable product identifier found in talend.project"
        }
