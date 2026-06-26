from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional


class MaterializedAnalysisCache:
    """JSON-backed cache for analysis and project state."""

    def __init__(self, cache_dir: str | Path = "output/cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_path = self.cache_dir / "analysis_cache.json"
        self.project_path = self.cache_dir / "project_cache.json"
        # In-memory read-through cache to avoid repeated disk reads
        self._analysis_mem: dict | None = None
        self._project_mem: dict | None = None

    def load_analysis(self) -> Dict[str, Any]:
        if self._analysis_mem is None:
            self._analysis_mem = self._load(self.analysis_path)
        return self._analysis_mem

    def load_project(self) -> Dict[str, Any]:
        if self._project_mem is None:
            self._project_mem = self._load(self.project_path)
        return self._project_mem

    def save_analysis(self, data: Dict[str, Any]) -> None:
        self._analysis_mem = data
        self._save(self.analysis_path, data)

    def save_project(self, data: Dict[str, Any]) -> None:
        self._project_mem = data
        self._save(self.project_path, data)

    def get_analysis(self, key: str, fingerprint: str = "") -> Optional[Any]:
        entry = self.load_analysis().get("entries", {}).get(key)
        if not entry:
            return None
        if fingerprint and entry.get("fingerprint", "") not in ("", fingerprint):
            return None
        return entry.get("value")

    def set_analysis(self, key: str, value: Any, fingerprint: str = "") -> None:
        data = self.load_analysis()
        data.setdefault("entries", {})[key] = {
            "fingerprint": fingerprint,
            "stored_at": time.time(),
            "value": value,
        }
        self.save_analysis(data)

    def clear(self) -> None:
        self._analysis_mem = {"version": 1, "entries": {}}
        self._project_mem = {"version": 1, "entries": {}}
        self.save_analysis(self._analysis_mem)
        self.save_project(self._project_mem)

    def _load(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {"version": 1, "entries": {}}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"version": 1, "entries": {}}

    def _save(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
