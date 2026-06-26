from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Mapping, Optional

from app.performance.cache_manager import AnalysisCacheManager, get_cache_manager


class IncrementalAnalysisFramework:
    """Cache-aware on-demand analysis for jobs, lineage paths, components, and assets."""

    def __init__(self, cache: Optional[AnalysisCacheManager] = None) -> None:
        self.cache = cache or get_cache_manager()

    def selected_job(self, jobs: Iterable[Mapping[str, Any]], job_name: str) -> Optional[Mapping[str, Any]]:
        for job in jobs or []:
            if job.get("job_data", {}).get("job_name") == job_name:
                return job
        return None

    def analyze_job360(
        self,
        jobs: Iterable[Mapping[str, Any]],
        job_name: str,
        producer: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    ) -> Any:
        job = self.selected_job(jobs, job_name)
        if job is None:
            return None
        fp = self.cache.fingerprint("job360", job_name, job)
        return self.cache.get_or_compute(
            f"job360:{job_name}",
            lambda: producer(job) if producer else self._default_job360(job),
            "analysis",
            True,
            fp,
        )

    def analyze_lineage_path(
        self,
        lineage: Mapping[str, Any],
        start_node: str,
        producer: Optional[Callable[[Mapping[str, Any], str], Any]] = None,
    ) -> Any:
        fp = self.cache.fingerprint("lineage_path", start_node, lineage)
        return self.cache.get_or_compute(
            f"lineage_path:{start_node}",
            lambda: producer(lineage, start_node) if producer else self._default_lineage_path(lineage, start_node),
            "analysis",
            True,
            fp,
        )

    def analyze_component(
        self,
        job: Mapping[str, Any],
        component_id: str,
        producer: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    ) -> Any:
        component = self._find_component(job, component_id)
        if component is None:
            return None
        fp = self.cache.fingerprint("component", job.get("job_data", {}).get("job_name"), component_id, component)
        return self.cache.get_or_compute(
            f"component:{component_id}",
            lambda: producer(component) if producer else component,
            "analysis",
            True,
            fp,
        )

    def analyze_asset(
        self,
        assets: Iterable[Mapping[str, Any]],
        asset_id: str,
        producer: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    ) -> Any:
        asset = next((a for a in assets or [] if str(a.get("id", a.get("asset_id", ""))) == str(asset_id)), None)
        if asset is None:
            return None
        fp = self.cache.fingerprint("asset", asset_id, asset)
        return self.cache.get_or_compute(
            f"asset:{asset_id}",
            lambda: producer(asset) if producer else asset,
            "analysis",
            True,
            fp,
        )

    def _default_job360(self, job: Mapping[str, Any]) -> Dict[str, Any]:
        data = job.get("job_data", {})
        return {
            "job_name": data.get("job_name"),
            "component_count": len(data.get("components", [])),
            "dependencies": job.get("dependencies", {}),
            "complexity": job.get("complexity", {}),
            "cloud_readiness": job.get("cloud_readiness", {}),
        }

    def _default_lineage_path(self, lineage: Mapping[str, Any], start_node: str) -> Dict[str, Any]:
        edges = list((lineage or {}).get("edges", []))
        path_edges = [edge for edge in edges if start_node in {str(edge.get("source", "")), str(edge.get("target", ""))}]
        return {"start_node": start_node, "edges": path_edges, "edge_count": len(path_edges)}

    def _find_component(self, job: Mapping[str, Any], component_id: str) -> Optional[Mapping[str, Any]]:
        for component in job.get("job_data", {}).get("components", []):
            values = {component.get("id"), component.get("unique_name"), component.get("component_id"), component.get("component_type")}
            if component_id in {str(value) for value in values if value is not None}:
                return component
        return None
