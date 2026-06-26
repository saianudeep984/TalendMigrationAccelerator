from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from app.performance.cache_manager import AnalysisCacheManager, get_cache_manager


class AnalysisRestoreEngine:
    """Restores persisted analyses into the active session."""

    def __init__(self, cache: Optional[AnalysisCacheManager] = None) -> None:
        self.cache = cache or get_cache_manager()

    def restore(self, keys: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        data = self.cache.materialized.load_analysis().get("entries", {})
        restored: Dict[str, Any] = {}
        wanted = set(keys) if keys else None
        for stored_key, entry in data.items():
            _, _, logical_key = stored_key.partition(":")
            logical_key = logical_key or stored_key
            if wanted and logical_key not in wanted:
                continue
            value = entry.get("value")
            self.cache.set("analysis", logical_key, value, persist=False)
            restored[logical_key] = value
        return restored

    def restore_to_session(self, key_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        restored = self.restore(key_map.keys() if key_map else None)
        for logical_key, value in restored.items():
            session_key = key_map.get(logical_key, logical_key) if key_map else logical_key
            self.cache.session[session_key] = value
        return restored
