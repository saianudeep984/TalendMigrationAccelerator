from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, Mapping, Optional


class GraphVirtualizer:
    """Builds visible graph subgraphs for depth-based expand-on-demand navigation."""

    def __init__(self, max_nodes: int = 250, max_edges: int = 500) -> None:
        self.max_nodes = max(1, int(max_nodes))
        self.max_edges = max(1, int(max_edges))

    def normalize(self, graph: Any) -> Dict[str, list[dict[str, Any]]]:
        if isinstance(graph, Mapping):
            nodes = list(graph.get("nodes", []))
            edges = list(graph.get("edges", []))
        else:
            nodes = [{"id": str(n)} for n in graph.nodes()]
            edges = [{"source": str(s), "target": str(t)} for s, t in graph.edges()]
        return {"nodes": [self._node(n) for n in nodes], "edges": [self._edge(e) for e in edges]}

    def visible_subgraph(
        self,
        graph: Any,
        roots: Optional[Iterable[str]] = None,
        depth: int = 1,
        expanded: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        normalized = self.normalize(graph)
        nodes = {str(n["id"]): n for n in normalized["nodes"]}
        adjacency: Dict[str, set[str]] = {node_id: set() for node_id in nodes}
        edge_lookup: Dict[tuple[str, str], dict[str, Any]] = {}
        for edge in normalized["edges"]:
            source, target = str(edge["source"]), str(edge["target"])
            adjacency.setdefault(source, set()).add(target)
            adjacency.setdefault(target, set()).add(source)
            edge_lookup[(source, target)] = edge
            edge_lookup.setdefault((target, source), edge)
        root_list = [str(r) for r in (roots or list(nodes)[:1]) if str(r) in nodes]
        expanded_set = {str(x) for x in (expanded or [])}
        visible_ids = self._walk(root_list, adjacency, depth, expanded_set)
        visible_ids = visible_ids[: self.max_nodes]
        visible = set(visible_ids)
        visible_edges = []
        for edge in normalized["edges"]:
            if str(edge["source"]) in visible and str(edge["target"]) in visible:
                visible_edges.append(edge)
                if len(visible_edges) >= self.max_edges:
                    break
        return {
            "nodes": [nodes[node_id] for node_id in visible_ids if node_id in nodes],
            "edges": visible_edges,
            "hidden_node_count": max(0, len(nodes) - len(visible_ids)),
            "hidden_edge_count": max(0, len(normalized["edges"]) - len(visible_edges)),
            "roots": root_list,
            "depth": depth,
        }

    def expand(self, graph: Any, node_id: str, current_nodes: Iterable[str], depth: int = 1) -> Dict[str, Any]:
        roots = set(str(n) for n in current_nodes)
        roots.add(str(node_id))
        return self.visible_subgraph(graph, roots=roots, depth=depth, expanded={node_id})

    def _walk(self, roots: list[str], adjacency: Mapping[str, set[str]], depth: int, expanded: set[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        queue = deque((root, 0) for root in roots)
        while queue and len(ordered) < self.max_nodes:
            node_id, distance = queue.popleft()
            if node_id in seen:
                continue
            seen.add(node_id)
            ordered.append(node_id)
            can_expand = distance < max(0, int(depth)) or node_id in expanded
            if can_expand:
                for neighbor in sorted(adjacency.get(node_id, [])):
                    if neighbor not in seen:
                        queue.append((neighbor, distance + 1))
        return ordered

    def _node(self, node: Any) -> dict[str, Any]:
        if isinstance(node, Mapping):
            data = dict(node)
            data["id"] = str(data.get("id"))
            return data
        return {"id": str(node)}

    def _edge(self, edge: Any) -> dict[str, Any]:
        if isinstance(edge, Mapping):
            source = edge.get("source", edge.get("source_node_id"))
            target = edge.get("target", edge.get("target_node_id"))
            data = dict(edge)
            data["source"] = str(source)
            data["target"] = str(target)
            return data
        source, target = edge
        return {"source": str(source), "target": str(target)}
