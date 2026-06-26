"""Component-level blast-radius analysis."""
from collections import defaultdict
from app.migration_intelligence.dependency_graph import DependencyGraphEngine


def _job_data(job):
    return job.get("job_data", job)


class ComponentImpactAnalyzer:
    def analyze(self, jobs, dependency_graph=None):
        jobs = list(jobs or [])
        graph = dependency_graph or DependencyGraphEngine().build(jobs)
        parents, children = defaultdict(set), defaultdict(set)
        for edge in graph.get("edges", []):
            if edge["source"] in graph.get("job_names", []) and edge["target"] in graph.get("job_names", []):
                children[edge["source"]].add(edge["target"]); parents[edge["target"]].add(edge["source"])
        rows = []
        for wrapper in jobs:
            data = _job_data(wrapper); job_name = data.get("job_name", "Unknown")
            components = data.get("components", []) or []
            links = data.get("connections", wrapper.get("connections", [])) or []
            before, after = defaultdict(set), defaultdict(set)
            for link in links:
                source = link.get("source", link.get("source_component", ""))
                target = link.get("target", link.get("target_component", ""))
                if source and target: after[source].add(target); before[target].add(source)
            affected_jobs = self._closure(job_name, parents, children)
            kind = str(data.get("job_type", wrapper.get("job_type", "job"))).lower()
            for index, component in enumerate(components):
                ctype = component.get("component_type", str(component)) if isinstance(component, dict) else str(component)
                uid = component.get("unique_name", component.get("name", f"{ctype}_{index + 1}")) if isinstance(component, dict) else f"{ctype}_{index + 1}"
                upstream, downstream = sorted(before[uid]), sorted(after[uid])
                cross_job = len(affected_jobs - {job_name})
                score = min(100, len(upstream) * 8 + len(downstream) * 12 + cross_job * 10 +
                            (20 if ctype in {"tRunJob", "tRESTRequest", "tESBProviderRequest"} else 0))
                rows.append({"component_id": f"{job_name}:{uid}", "component_type": ctype, "unique_name": uid,
                             "job_name": job_name, "upstream_components": upstream, "downstream_components": downstream,
                             "affected_jobs": sorted(affected_jobs), "affected_subjobs": sorted(children[job_name]),
                             "affected_routes": sorted(affected_jobs) if "route" in kind else [],
                             "affected_services": sorted(affected_jobs) if "service" in kind else [],
                             "impact_score": score, "impact": self.classify(score)})
        return {"components": sorted(rows, key=lambda x: (-x["impact_score"], x["component_id"])),
                "summary": self._summary(rows)}

    @staticmethod
    def _closure(job, parents, children):
        seen, pending = {job}, [job]
        while pending:
            node = pending.pop()
            for other in parents[node] | children[node]:
                if other not in seen: seen.add(other); pending.append(other)
        return seen

    @staticmethod
    def classify(score):
        return "LOW" if score < 25 else "MEDIUM" if score < 50 else "HIGH" if score < 75 else "CRITICAL"

    @staticmethod
    def _summary(rows):
        return {level: sum(r["impact"] == level for r in rows) for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")}

    analyze_project = analyze
