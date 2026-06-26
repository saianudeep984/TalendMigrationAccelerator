from itertools import islice
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import networkx as nx

from app.tiap.models.repository import build_adjacency_from_jobs, normalize_name


class DependencyGraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

    def build(self, all_jobs: Sequence[Dict[str, Any]]) -> nx.DiGraph:
        self.graph.clear()
        adjacency = build_adjacency_from_jobs(all_jobs)
        for parent, children in adjacency.items():
            self.graph.add_node(parent)
            for child in children:
                self.graph.add_node(child)
                self.graph.add_edge(parent, child, relationship="tRunJob")
        return self.graph

    def build_from_relationships(self, relationships: Iterable[Tuple[str, str]]) -> nx.DiGraph:
        self.graph.clear()
        for parent, child in relationships:
            parent = normalize_name(parent)
            child = normalize_name(child)
            if parent and child:
                self.graph.add_edge(parent, child, relationship="tRunJob")
        return self.graph

    def analyze(self, all_jobs: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        graph = self.build(all_jobs)
        cycles = [list(cycle) for cycle in nx.simple_cycles(graph)]
        chains = self._dependency_chains(graph)
        critical_paths = self._critical_paths(graph, cycles)
        return {
            "relationships": [(u, v) for u, v in graph.edges()],
            "parent_jobs": sorted([n for n in graph.nodes if graph.out_degree(n) > 0]),
            "child_jobs": sorted([n for n in graph.nodes if graph.in_degree(n) > 0]),
            "dependency_chains": chains,
            "critical_paths": critical_paths,
            "circular_dependencies": cycles,
            "missing_child_jobs": sorted([n for n in graph.nodes if graph.in_degree(n) > 0 and graph.out_degree(n) == 0]),
            "dependency_statistics": {
                "nodes": graph.number_of_nodes(),
                "edges": graph.number_of_edges(),
                "parent_jobs": len([n for n in graph.nodes if graph.out_degree(n) > 0]),
                "child_jobs": len([n for n in graph.nodes if graph.in_degree(n) > 0]),
                "circular_dependencies": len(cycles),
                "max_depth": max((len(path) - 1 for path in chains), default=0),
            },
            "graph": graph,
            "graph_object": graph,
        }

    def export_graph_data(self) -> Dict[str, Any]:
        return {
            "nodes": [{"id": node, "in_degree": self.graph.in_degree(node), "out_degree": self.graph.out_degree(node)} for node in self.graph.nodes()],
            "edges": [{"source": source, "target": target, **data} for source, target, data in self.graph.edges(data=True)],
        }

    def _dependency_chains(self, graph: nx.DiGraph) -> List[List[str]]:
        if graph.number_of_nodes() == 0:
            return []
        roots = [n for n in graph.nodes if graph.in_degree(n) == 0] or list(graph.nodes)
        leaves = [n for n in graph.nodes if graph.out_degree(n) == 0] or list(graph.nodes)
        chains = []
        remaining = 100
        for root in roots:
            if remaining <= 0:
                break
            for leaf in leaves:
                if remaining <= 0:
                    break
                if root == leaf:
                    continue
                try:
                    paths = nx.all_simple_paths(graph, root, leaf, cutoff=50)
                    for path in islice(paths, remaining):
                        chains.append(path)
                        remaining -= 1
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
        chains.sort(key=lambda path: (-len(path), path))
        return chains

    def _critical_paths(self, graph: nx.DiGraph, cycles: List[List[str]]) -> List[List[str]]:
        if cycles:
            return sorted(cycles, key=lambda path: (-len(path), path))[:20]
        try:
            return [nx.dag_longest_path(graph)] if graph.number_of_edges() else []
        except Exception:
            return []


def build_dependency_graph(all_jobs):
    return DependencyGraphBuilder().analyze(all_jobs)
