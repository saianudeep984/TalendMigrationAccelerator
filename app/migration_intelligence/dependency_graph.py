"""Complete cross-job dependency graph."""
import json
import re
from pathlib import Path


def _data(job):
    return job.get("job_data", job)


def _values(component):
    values = component.get("parameters", component.get("element_parameters", {})) if isinstance(component, dict) else {}
    if isinstance(values, dict):
        return [str(v) for v in values.values()]
    return [str(v.get("value", "")) for v in values if isinstance(v, dict)] if isinstance(values, list) else []


class DependencyGraphEngine:
    EDGE_TYPES = ("parent_child", "trigger", "shared_context", "routine", "metadata", "lineage")

    def build(self, jobs, lineage_service=None):
        jobs = list(jobs or [])
        names = {_data(j).get("job_name", "Unknown") for j in jobs}
        nodes = {n: {"id": n, "label": n, "type": "job"} for n in names}
        edges = set()
        assets = {"context": {}, "routine": {}, "metadata": {}}
        for job in jobs:
            data, name = _data(job), _data(job).get("job_name", "Unknown")
            deps = job.get("dependencies", {})
            children = set(deps.get("child_jobs", []) or data.get("child_jobs", []) or [])
            for component in data.get("components", []) or []:
                ctype = component.get("component_type", "") if isinstance(component, dict) else ""
                vals = _values(component)
                if ctype == "tRunJob":
                    for value in vals:
                        candidate = value.strip("\"'").replace(".item", "")
                        candidate = re.sub(r"_\d+\.\d+$", "", candidate)
                        if candidate in names: children.add(candidate)
                if ctype in {"tPreJob", "tPostJob", "tRunJob"}:
                    for child in children: edges.add((name, child, "trigger" if ctype != "tRunJob" else "parent_child"))
            for child in children:
                if child in names: edges.add((name, child, "parent_child"))
            groups = {
                "context": deps.get("contexts", data.get("contexts", [])) or [],
                "routine": deps.get("routines", data.get("routines", [])) or [],
                "metadata": deps.get("metadata_connections", data.get("metadata_connections", [])) or [],
            }
            for kind, values in groups.items():
                for value in values:
                    key = value.get("name", str(value)) if isinstance(value, dict) else str(value)
                    assets[kind].setdefault(key, set()).add(name)
        for kind, grouped in assets.items():
            for asset, users in grouped.items():
                asset_id = f"{kind}:{asset}"
                nodes[asset_id] = {"id": asset_id, "label": asset, "type": kind}
                for user in users: edges.add((user, asset_id, "shared_context" if kind == "context" else kind))
        if lineage_service:
            for source in names:
                for target in lineage_service.downstream_jobs(source):
                    if target in names: edges.add((source, target, "lineage"))
        payload = {"nodes": list(nodes.values()),
                   "edges": [{"source": s, "target": t, "type": k} for s, t, k in sorted(edges)],
                   "job_names": sorted(names)}
        payload["adjacency"] = self._adjacency(payload)
        return payload

    build_graph = build

    @staticmethod
    def _adjacency(graph):
        result = {n: [] for n in graph.get("job_names", [])}
        for edge in graph.get("edges", []):
            if edge["source"] in result and edge["target"] in result:
                result[edge["source"]].append(edge["target"])
        return {k: sorted(set(v)) for k, v in result.items()}

    @staticmethod
    def save(graph, path):
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
        return str(path)
