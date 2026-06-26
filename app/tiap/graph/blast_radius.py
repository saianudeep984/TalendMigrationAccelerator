from typing import Any, Dict, Sequence

import networkx as nx

from app.tiap.graph.dependency_graph_builder import DependencyGraphBuilder
from app.tiap.models.repository import component_parameters, iter_job_data, normalize_name


class BlastRadiusEngine:
    def analyze(self, all_jobs: Sequence[Dict[str, Any]], job_name: str) -> Dict[str, Any]:
        target = normalize_name(job_name)
        graph = DependencyGraphBuilder().build(all_jobs)
        if target not in graph:
            return {
                "job_name": target,
                "impacted_jobs": [],
                "impacted_contexts": [],
                "impacted_joblets": [],
                "impacted_routines": [],
                "impacted_metadata": [],
                "blast_radius_score": 0,
                "risk": "LOW",
            }

        impacted_jobs = sorted(nx.descendants(graph, target))
        selected = {target, *impacted_jobs}
        contexts, joblets, routines, metadata = set(), set(), set(), set()

        for data in iter_job_data(all_jobs):
            name = normalize_name(data.get("job_name"))
            if name not in selected:
                continue
            for ctx in data.get("contexts", []):
                if isinstance(ctx, dict) and ctx.get("name"):
                    contexts.add(str(ctx["name"]))
            for component in data.get("components", []):
                if not isinstance(component, dict):
                    continue
                ctype = component.get("component_type", "")
                params = component_parameters(component)
                if ctype.lower().startswith("tjoblet") or ctype == "tJoblet":
                    joblets.add(params.get("JOBLET") or params.get("PROCESS") or component.get("unique_name") or ctype)
                for value in params.values():
                    text = str(value)
                    if "context." in text:
                        import re
                        contexts.update(re.findall(r"context\.([A-Za-z_][A-Za-z0-9_]*)", text))
                    import re
                    routines.update(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", text))
                    if "metadata" in text.lower() or "repository" in text.lower():
                        metadata.add(normalize_name(text.split("/")[-1]))

        score = min(100, len(impacted_jobs) * 12 + len(contexts) * 5 + len(joblets) * 10 + len(routines) * 7 + len(metadata) * 4)
        risk = "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"
        return {
            "job_name": target,
            "impacted_jobs": impacted_jobs,
            "impacted_contexts": sorted(contexts),
            "impacted_joblets": sorted(joblets),
            "impacted_routines": sorted(routines),
            "impacted_metadata": sorted(metadata),
            "blast_radius_score": score,
            "risk": risk,
        }


def blast_radius(graph_or_jobs, job_name):
    if hasattr(graph_or_jobs, "nodes"):
        graph = graph_or_jobs
        impacted = sorted(nx.descendants(graph, normalize_name(job_name))) if normalize_name(job_name) in graph else []
        score = min(100, len(impacted) * 12)
        return {"impacted_jobs": impacted, "blast_radius_score": score, "risk": "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"}
    return BlastRadiusEngine().analyze(graph_or_jobs, job_name)
