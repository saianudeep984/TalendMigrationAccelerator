from __future__ import annotations

from typing import Any, Dict, Optional

from app.performance.cache_manager import AnalysisCacheManager, get_cache_manager


class CacheInvalidationEngine:
    """Invalidates only on repository/config changes or explicit refresh."""

    def __init__(self, cache: Optional[AnalysisCacheManager] = None) -> None:
        self.cache = cache or get_cache_manager()

    def evaluate(
        self,
        zip_fingerprint: Optional[str] = None,
        config_fingerprint: Optional[str] = None,
        manual_refresh: bool = False,
        state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        state = state if state is not None else self.cache.session
        previous_zip = state.get("_tma_zip_fingerprint")
        previous_config = state.get("_tma_config_fingerprint")
        changed = manual_refresh
        changed = changed or (zip_fingerprint is not None and previous_zip not in (None, zip_fingerprint))
        changed = changed or (config_fingerprint is not None and previous_config not in (None, config_fingerprint))
        if changed:
            self.cache.invalidate()
        if zip_fingerprint is not None:
            state["_tma_zip_fingerprint"] = zip_fingerprint
        if config_fingerprint is not None:
            state["_tma_config_fingerprint"] = config_fingerprint
        return changed
