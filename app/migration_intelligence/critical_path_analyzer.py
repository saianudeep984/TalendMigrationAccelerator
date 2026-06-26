"""Dependency criticality and execution-chain analysis."""
import networkx as nx


class CriticalPathAnalyzer:
    def analyze(self, graph, business_critical_jobs=None):
        jobs = set(graph.get("job_names", [])); g = nx.DiGraph(); g.add_nodes_from(jobs)
        for edge in graph.get("edges", []):
            if edge["source"] in jobs and edge["target"] in jobs:
                g.add_edge(edge["source"], edge["target"])
        critical = set(business_critical_jobs or [])
        rows = []
        for node in sorted(g):
            descendants = nx.descendants(g, node)
            fan_out = g.out_degree(node)
            depth = self._depth(g, node)
            score = min(100, round(len(descendants) * 8 + fan_out * 12 + depth * 10 + (20 if node in critical else 0)))
            rows.append({"job_name": node, "downstream_impact": len(descendants), "fan_out": fan_out,
                         "dependency_depth": depth, "criticality_score": score,
                         "business_critical": node in critical})
        chains = self._chains(g)
        return {"jobs": sorted(rows, key=lambda r: (-r["criticality_score"], r["job_name"])),
                "critical_paths": chains[:10], "max_depth": max((len(c) - 1 for c in chains), default=0)}

    @staticmethod
    def _depth(g, node):
        if not nx.is_directed_acyclic_graph(g):
            return len(nx.descendants(g, node))
        return max((len(p) - 1 for target in nx.descendants(g, node) for p in nx.all_simple_paths(g, node, target)), default=0)

    @staticmethod
    def _chains(g):
        if not nx.is_directed_acyclic_graph(g):
            condensed = nx.condensation(g); return [list(nx.dag_longest_path(condensed))]
        sources = [n for n in g if g.in_degree(n) == 0]
        sinks = [n for n in g if g.out_degree(n) == 0]
        paths = [p for s in sources for t in sinks for p in nx.all_simple_paths(g, s, t)]
        return sorted(paths, key=lambda p: (-len(p), tuple(p)))

    analyze_paths = analyze
