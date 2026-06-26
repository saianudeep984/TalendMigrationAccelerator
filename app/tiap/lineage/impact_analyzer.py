from typing import Any, Dict, Sequence

import networkx as nx

from app.tiap.graph.blast_radius import BlastRadiusEngine
from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder
from app.tiap.models.repository import component_parameters, iter_job_data, normalize_name


class ImpactAnalyzer:
    def analyze(self, all_jobs: Sequence[Dict[str, Any]], job_name: str) -> Dict[str, Any]:
        target = normalize_name(job_name)
        graph = DependencyGraphBuilder().build(all_jobs)
        blast = BlastRadiusEngine().analyze(all_jobs, target)
        upstream = sorted(nx.ancestors(graph, target)) if target in graph else []
        downstream = blast["impacted_jobs"]
        current = self._current_assets(all_jobs, target)
        return {
            "job_name": target,
            "impact_tree": self._tree(target, upstream, downstream, current),
            "dependency_tree": {
                "used_by": upstream,
                "uses": downstream,
            },
            "critical_path_analysis": self._critical_paths(graph, target),
            "used_by_count": len(upstream),
            "uses_joblets": current["joblets"],
            "uses_context_groups": current["contexts"],
            "uses_routines": current["routines"],
            "blast_radius": blast,
        }

    def _current_assets(self, all_jobs, target):
        assets = {"contexts": [], "joblets": [], "routines": [], "metadata": []}
        for data in iter_job_data(all_jobs):
            if normalize_name(data.get("job_name")) != target:
                continue
            for ctx in data.get("contexts", []):
                if isinstance(ctx, dict) and ctx.get("name"):
                    assets["contexts"].append(str(ctx["name"]))
            for component in data.get("components", []):
                if not isinstance(component, dict):
                    continue
                params = component_parameters(component)
                if component.get("component_type", "").lower().startswith("tjoblet"):
                    assets["joblets"].append(params.get("JOBLET") or component.get("unique_name", "tJoblet"))
                for value in params.values():
                    import re
                    assets["routines"].extend(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", str(value)))
            break
        return {key: sorted(set(value)) for key, value in assets.items()}

    def _tree(self, target, upstream, downstream, assets):
        return {
            "label": target,
            "children": [
                {"label": f"Used By {len(upstream)} Jobs", "children": upstream},
                {"label": f"Uses {len(assets['joblets'])} Joblets", "children": assets["joblets"]},
                {"label": f"Uses {len(assets['contexts'])} Context Groups", "children": assets["contexts"]},
                {"label": f"Uses {len(assets['routines'])} Routines", "children": assets["routines"]},
                {"label": f"Impacts {len(downstream)} Jobs", "children": downstream},
            ],
        }

    def _critical_paths(self, graph, target):
        if target not in graph:
            return []
        paths = []
        for source in graph.nodes:
            for sink in graph.nodes:
                if source == sink:
                    continue
                try:
                    for path in nx.all_simple_paths(graph, source, sink, cutoff=50):
                        if target in path:
                            paths.append(path)
                except Exception:
                    continue
        return sorted(paths, key=lambda path: (-len(path), path))[:20]


def analyze_impact(all_jobs, job_name):
    return ImpactAnalyzer().analyze(all_jobs, job_name)
