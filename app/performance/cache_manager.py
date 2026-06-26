from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, Iterable, Optional

from app.performance.cache_metrics import CacheMetricsEngine, get_cache_metrics
from app.performance.materialized_cache import MaterializedAnalysisCache

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None


ANALYSIS_KEYS = {
    "readiness_analysis",
    "lineage_analysis",
    "dependency_graph",
    "impact_analysis",
    "framework_analysis",
    "upgrade_advisor",
    "migration_intelligence",
    "portfolio_analytics",
    "architecture_analysis",
    "migration_runbook",
}


class AnalysisCacheManager:
    """Central cache facade over session state, memory, and JSON materialization."""

    def __init__(
        self,
        materialized: Optional[MaterializedAnalysisCache] = None,
        metrics: Optional[CacheMetricsEngine] = None,
        session: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.materialized = materialized or MaterializedAnalysisCache()
        self.metrics = metrics or get_cache_metrics()
        self.session = session if session is not None else self._session()
        self.session.setdefault("_tma_project_cache", {})
        self.session.setdefault("_tma_analysis_cache", {})
        self.session.setdefault("_tma_ui_cache", {})
        self.session.setdefault("_tma_cache_meta", {})

    def _session(self) -> Dict[str, Any]:
        if st is not None:
            try:
                return st.session_state
            except Exception:
                pass
        return {}

    def fingerprint(self, *parts: Any) -> str:
        raw = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]

    def get(self, namespace: str, key: str, default: Any = None, fingerprint: str = "") -> Any:
        bucket = self._bucket(namespace)
        meta_key = f"{namespace}:{key}"
        if key in bucket:
            meta = self.session.setdefault("_tma_cache_meta", {}).get(meta_key, {})
            if not fingerprint or meta.get("fingerprint", "") in ("", fingerprint):
                self.metrics.record_hit(namespace)
                return bucket[key]
            bucket.pop(key, None)
        if namespace == "analysis":
            restored = self.materialized.get_analysis(meta_key, fingerprint=fingerprint)
            if restored is not None:
                bucket[key] = restored
                self.session["_tma_cache_meta"][meta_key] = {"fingerprint": fingerprint}
                self.metrics.record_hit(namespace)
                return restored
        self.metrics.record_miss(namespace)
        return default

    def set(self, namespace: str, key: str, value: Any, persist: bool = False, fingerprint: str = "") -> Any:
        self._bucket(namespace)[key] = value
        self.session.setdefault("_tma_cache_meta", {})[f"{namespace}:{key}"] = {"fingerprint": fingerprint}
        self.metrics.record_write(namespace, value)
        if persist and namespace == "analysis":
            self.materialized.set_analysis(f"{namespace}:{key}", value, fingerprint)
        elif persist and namespace == "project":
            project = self.materialized.load_project()
            project.setdefault("entries", {})[key] = {"fingerprint": fingerprint, "value": value}
            self.materialized.save_project(project)
        return value

    def get_or_compute(
        self,
        key: str,
        producer: Callable[[], Any],
        namespace: str = "analysis",
        persist: bool = True,
        fingerprint: str = "",
    ) -> Any:
        cached = self.get(namespace, key, None, fingerprint=fingerprint)
        if cached is not None:
            return cached
        value = producer()
        return self.set(namespace, key, value, persist=persist, fingerprint=fingerprint)

    def cache_analysis(self, analysis_key: str, producer: Callable[[], Any], fingerprint: str = "") -> Any:
        return self.get_or_compute(analysis_key, producer, "analysis", True, fingerprint)

    def invalidate(self, namespaces: Optional[Iterable[str]] = None, materialized: bool = True) -> None:
        names = list(namespaces or ("project", "analysis", "ui"))
        for namespace in names:
            self._bucket(namespace).clear()
            self.metrics.record_invalidation(namespace)
        for meta_key in list(self.session.setdefault("_tma_cache_meta", {})):
            if meta_key.split(":", 1)[0] in names:
                self.session["_tma_cache_meta"].pop(meta_key, None)
        if materialized and ("analysis" in names or "project" in names):
            self.materialized.clear()

    def metrics_snapshot(self) -> Dict[str, Any]:
        return self.metrics.snapshot()

    def _bucket(self, namespace: str) -> Dict[str, Any]:
        mapping = {
            "project": "_tma_project_cache",
            "analysis": "_tma_analysis_cache",
            "ui": "_tma_ui_cache",
        }
        return self.session.setdefault(mapping.get(namespace, namespace), {})


@st.cache_resource(show_spinner=False)
def get_cache_manager() -> AnalysisCacheManager:
    return AnalysisCacheManager()
