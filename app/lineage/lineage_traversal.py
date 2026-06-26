"""
lineage_traversal.py
====================
Multi-hop forward and backward lineage traversal built on top of
``LineageGraph`` / ``LineagePath`` from ``lineage_model.py``.

This module is the traversal layer described in the Phase 3 architecture
review.  It intentionally has *no* knowledge of how a graph was built
(parser details, ColumnMapping shapes, etc.) and *no* Streamlit dependency —
it operates purely on ``LineageGraph`` / ``LineageNode`` / ``LineageEdge``
objects and returns ``LineagePath`` instances that callers can inspect,
serialise, or render however they like.

Public API
----------
::

    trace_backward(
        graph      : LineageGraph,
        start_node_id : str,
        *,
        max_hops   : int  = 20,
        edge_types : Optional[Collection[EdgeType]] = None,
        node_filter: Optional[Callable[[LineageNode], bool]] = None,
    ) -> TraversalResult

    trace_forward(
        graph      : LineageGraph,
        start_node_id : str,
        *,
        max_hops   : int  = 20,
        edge_types : Optional[Collection[EdgeType]] = None,
        node_filter: Optional[Callable[[LineageNode], bool]] = None,
    ) -> TraversalResult

Both return a ``TraversalResult`` dataclass with:
    ``paths``          – list[LineagePath] ordered by hop count (shortest first)
    ``visited_nodes``  – set[str]  all node ids reached
    ``truncated_paths``– list[LineagePath] paths cut short by hop limit / cycle
    ``cycles_detected``– list[list[str]]  each inner list is a cycle node-id chain
    ``stats``          – TraversalStats  timing + count summary

Helper
------
::

    find_paths_between(
        graph      : LineageGraph,
        source_id  : str,
        target_id  : str,
        *,
        max_hops   : int  = 20,
        edge_types : Optional[Collection[EdgeType]] = None,
    ) -> list[LineagePath]

Design notes
------------
*  BFS (not DFS) so the ``paths`` list is shortest-first and the hop
   limit fires at the right depth.
*  Cycle detection: a path that would revisit a node it has already
   passed through is terminated immediately and the cycle is recorded;
   the graph is never modified.
*  ``max_hops`` is a per-path limit (not a global node-visit limit) so
   callers get *all* paths up to that depth rather than an arbitrary
   subset cut off by node-visit deduplication.
*  ``edge_types`` allows callers to restrict traversal to e.g. only
   DATA_FLOW edges (skipping LOOKUP edges) for a cleaner impact analysis.
*  ``node_filter`` allows callers to prune the search tree by node
   attributes (e.g. only follow edges that enter a SOURCE_TABLE node
   when walking backward).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Collection, Optional

from app.lineage.lineage_model import (
    EdgeType,
    LineageEdge,
    LineageGraph,
    LineageNode,
    LineagePath,
)

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Traversal cache
# ────────────────────────────────────────────────────────────────────────────
# Keyed on graph identity + a cheap structural fingerprint (node/edge counts)
# so a mutated graph object naturally invalidates its entries. Skipped when a
# node_filter callable is supplied (not safely cacheable). Results are
# returned directly; callers should treat TraversalResult as read-only.
_TRAVERSAL_CACHE: dict[tuple, "TraversalResult"] = {}
_TRAVERSAL_CACHE_LOCK = threading.Lock()


def _traversal_cache_key(
    graph: LineageGraph,
    start_node_id: str,
    direction: str,
    max_hops: int,
    edge_types: Optional[Collection[EdgeType]],
) -> tuple:
    edge_types_key = tuple(sorted(et.value for et in edge_types)) if edge_types else None
    return (
        id(graph),
        graph.node_count,
        graph.edge_count,
        start_node_id,
        direction,
        max_hops,
        edge_types_key,
    )


def clear_traversal_cache() -> None:
    """Drop all cached traversal results."""
    with _TRAVERSAL_CACHE_LOCK:
        _TRAVERSAL_CACHE.clear()

# ────────────────────────────────────────────────────────────────────────────
# Result types
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class TraversalStats:
    """Timing and count summary for one traversal call."""

    direction: str          # "backward" | "forward"
    start_node_id: str
    elapsed_seconds: float = 0.0
    nodes_visited: int = 0
    paths_completed: int = 0
    paths_truncated: int = 0
    cycles_detected: int = 0
    max_hops_allowed: int = 0
    max_hops_reached: int = 0

    def summary(self) -> str:
        return (
            f"[{self.direction}] start={self.start_node_id!r}  "
            f"visited={self.nodes_visited}  paths={self.paths_completed}  "
            f"truncated={self.paths_truncated}  cycles={self.cycles_detected}  "
            f"max_depth={self.max_hops_reached}/{self.max_hops_allowed}  "
            f"elapsed={self.elapsed_seconds:.4f}s"
        )


@dataclass
class TraversalResult:
    """
    Full result of a ``trace_backward()`` or ``trace_forward()`` call.

    Attributes
    ----------
    paths : list[LineagePath]
        All complete paths found, ordered shortest-first.
        A path is "complete" when no further hops are available
        (i.e. the frontier node has no more incoming/outgoing edges)
        *or* when it reaches the ``max_hops`` limit.
    truncated_paths : list[LineagePath]
        Paths that hit ``max_hops`` before reaching a natural terminus.
        Included here for inspection rather than silently dropped.
    cycles_detected : list[list[str]]
        Each entry is an ordered list of node ids forming one detected
        cycle, starting at the node where the revisit was detected and
        ending at the node id that was about to be revisited.
        E.g. ``["A", "B", "C", "A"]`` means: following the path
        A→B→C we saw that the next hop would return to A.
    visited_nodes : set[str]
        All node ids encountered during the traversal (regardless of
        whether they appear in a complete path).
    stats : TraversalStats
        Timing and count summary.
    """

    paths: list[LineagePath] = field(default_factory=list)
    truncated_paths: list[LineagePath] = field(default_factory=list)
    cycles_detected: list[list[str]] = field(default_factory=list)
    visited_nodes: set[str] = field(default_factory=set)
    stats: TraversalStats = field(
        default_factory=lambda: TraversalStats(
            direction="", start_node_id=""
        )
    )

    # -- convenience accessors -------------------------------------------

    @property
    def all_paths(self) -> list[LineagePath]:
        """Complete paths + truncated paths, shortest-first."""
        return sorted(
            self.paths + self.truncated_paths,
            key=lambda p: p.hop_count,
        )

    @property
    def has_cycles(self) -> bool:
        return bool(self.cycles_detected)

    def shortest_path(self) -> Optional[LineagePath]:
        """Return the shortest complete path, or None if none found."""
        return self.paths[0] if self.paths else None

    def longest_path(self) -> Optional[LineagePath]:
        """Return the longest complete path, or None if none found."""
        return self.paths[-1] if self.paths else None

    def paths_through_node(self, node_id: str) -> list[LineagePath]:
        """Return all complete paths that pass through ``node_id``."""
        return [
            p for p in self.paths
            if any(n.id == node_id for n in p.nodes)
        ]

    def to_dict(self) -> dict:
        return {
            "paths": [p.to_dict() for p in self.paths],
            "truncated_paths": [p.to_dict() for p in self.truncated_paths],
            "cycles_detected": self.cycles_detected,
            "visited_nodes": sorted(self.visited_nodes),
            "stats": {
                "direction": self.stats.direction,
                "start_node_id": self.stats.start_node_id,
                "elapsed_seconds": round(self.stats.elapsed_seconds, 6),
                "nodes_visited": self.stats.nodes_visited,
                "paths_completed": self.stats.paths_completed,
                "paths_truncated": self.stats.paths_truncated,
                "cycles_detected": self.stats.cycles_detected,
                "max_hops_allowed": self.stats.max_hops_allowed,
                "max_hops_reached": self.stats.max_hops_reached,
            },
        }


# ────────────────────────────────────────────────────────────────────────────
# Internal BFS engine
# ────────────────────────────────────────────────────────────────────────────

def _bfs(
    graph: LineageGraph,
    start_node_id: str,
    direction: str,            # "backward" | "forward"
    max_hops: int,
    edge_types: Optional[Collection[EdgeType]],
    node_filter: Optional[Callable[[LineageNode], bool]],
) -> TraversalResult:
    """
    Core BFS engine shared by trace_backward() and trace_forward().

    direction="forward"  → follows outgoing edges (source→target)
    direction="backward" → follows incoming edges (target→source,
                           but edges are stored in forward direction
                           so we traverse edge.source_node_id when
                           coming from edge.target_node_id)
    """
    t0 = time.perf_counter()

    cache_key = None
    if node_filter is None:
        cache_key = _traversal_cache_key(graph, start_node_id, direction, max_hops, edge_types)
        with _TRAVERSAL_CACHE_LOCK:
            cached = _TRAVERSAL_CACHE.get(cache_key)
        if cached is not None:
            logger.debug("_bfs: cache hit for %r start=%r", direction, start_node_id)
            return cached

    result = TraversalResult()
    result.stats = TraversalStats(
        direction=direction,
        start_node_id=start_node_id,
        max_hops_allowed=max_hops,
    )

    if graph.is_empty:
        logger.debug("_bfs: graph is empty, nothing to traverse")
        result.stats.elapsed_seconds = time.perf_counter() - t0
        if cache_key is not None:
            with _TRAVERSAL_CACHE_LOCK:
                _TRAVERSAL_CACHE[cache_key] = result
        return result

    # Validate start node
    start_node = graph.get_node(start_node_id)
    if start_node is None:
        logger.warning(
            "_bfs: start_node_id %r not found in graph (%d nodes)",
            start_node_id,
            graph.node_count,
        )
        result.stats.elapsed_seconds = time.perf_counter() - t0
        if cache_key is not None:
            with _TRAVERSAL_CACHE_LOCK:
                _TRAVERSAL_CACHE[cache_key] = result
        return result

    result.visited_nodes.add(start_node_id)

    # BFS queue: each entry is a LineagePath being grown
    # We use a deque for O(1) popleft()
    queue: deque[LineagePath] = deque()
    queue.append(LineagePath.single_node(start_node))

    max_depth_seen = 0

    while queue:
        current_path = queue.popleft()

        # For forward traversal we grow from the tail; for backward we grow
        # from the head (because _prepend_hop prepends ancestors at the front).
        if direction == "forward":
            frontier_node = current_path.end_node
        else:
            frontier_node = current_path.start_node

        # Collect next edges from frontier node
        if direction == "forward":
            next_edges: list[LineageEdge] = graph.outgoing_edges(frontier_node.id)
        else:
            # Backward: follow incoming edges (walk toward their source)
            next_edges = graph.incoming_edges(frontier_node.id)

        # Filter by edge type if requested
        if edge_types is not None:
            next_edges = [e for e in next_edges if e.edge_type in edge_types]

        # Terminal: no more edges to follow → this path is complete
        if not next_edges:
            if current_path.hop_count > 0:   # skip the zero-hop seed
                result.paths.append(current_path)
                result.stats.paths_completed += 1
            continue

        extended = False

        for edge in next_edges:
            # Resolve the next node in the traversal direction
            if direction == "forward":
                next_node_id = edge.target_node_id
            else:
                next_node_id = edge.source_node_id

            next_node = graph.get_node(next_node_id)
            if next_node is None:
                continue  # dangling edge (shouldn't happen in a well-formed graph)

            # ── Cycle detection ──────────────────────────────────────────
            path_node_ids = {n.id for n in current_path.nodes}
            if next_node_id in path_node_ids:
                full_chain = [n.id for n in current_path.nodes] + [next_node_id]
                # Trim to just the loop itself: from the earlier occurrence
                # of next_node_id through to its revisit, so the recorded
                # chain always starts and ends on the same node id.
                loop_start = full_chain.index(next_node_id)
                cycle_chain = full_chain[loop_start:]
                if cycle_chain[0] == cycle_chain[-1] and cycle_chain not in result.cycles_detected:
                    result.cycles_detected.append(cycle_chain)
                    result.stats.cycles_detected += 1
                logger.debug(
                    "_bfs: cycle detected at %r (path len=%d)",
                    next_node_id, current_path.hop_count,
                )
                # Treat the current path (up to but not including the cycle)
                # as a completed path if it has at least one hop
                if current_path.hop_count > 0 and current_path not in result.paths:
                    result.paths.append(current_path)
                    result.stats.paths_completed += 1
                extended = True   # mark so we don't double-add below
                continue

            # ── Optional node filter ──────────────────────────────────────
            if node_filter is not None and not node_filter(next_node):
                continue

            result.visited_nodes.add(next_node_id)

            # ── Hop limit ────────────────────────────────────────────────
            if current_path.hop_count >= max_hops:
                truncated = current_path  # already at limit; can't extend
                if truncated not in result.truncated_paths:
                    result.truncated_paths.append(truncated)
                    result.stats.paths_truncated += 1
                logger.debug(
                    "_bfs: hop limit %d reached at %r",
                    max_hops, frontier_node.id,
                )
                extended = True
                continue

            # ── Extend the path ──────────────────────────────────────────
            # For backward traversal we invert the edge direction in the
            # LineagePath so that paths[i].nodes[0] is always the furthest
            # ancestor and paths[i].nodes[-1] is the start node.
            if direction == "backward":
                # Build a new forward-direction edge for the path so that
                # LineagePath invariants (source→target match) hold:
                # the logical direction in the path is ancestor → start,
                # but the stored edge already points source→target in the
                # graph.  We keep the edge as-is and note the direction in
                # the path so callers can reason about it.
                # We extend by prepending: next_node → ... → start
                # To keep LineagePath invariants we rebuild with prepend.
                extended_path = _prepend_hop(current_path, edge, next_node)
            else:
                extended_path = current_path.extend(edge, next_node)

            new_depth = extended_path.hop_count
            if new_depth > max_depth_seen:
                max_depth_seen = new_depth

            queue.append(extended_path)
            extended = True

        # If no branches were taken AND this path has hops, it's a terminus
        if not extended and current_path.hop_count > 0:
            result.paths.append(current_path)
            result.stats.paths_completed += 1

    # Final stats
    result.stats.nodes_visited = len(result.visited_nodes)
    result.stats.max_hops_reached = max_depth_seen
    result.stats.elapsed_seconds = time.perf_counter() - t0

    # Sort complete paths shortest-first
    result.paths.sort(key=lambda p: p.hop_count)
    result.truncated_paths.sort(key=lambda p: p.hop_count)

    logger.info("_bfs: %s", result.stats.summary())
    if cache_key is not None:
        with _TRAVERSAL_CACHE_LOCK:
            _TRAVERSAL_CACHE[cache_key] = result
    return result


def _prepend_hop(
    path: LineagePath,
    edge: LineageEdge,
    ancestor_node: LineageNode,
) -> LineagePath:
    """
    Return a new LineagePath with ``ancestor_node`` prepended.

    Used by trace_backward() to build paths in ancestor → ... → start
    order while keeping LineagePath node/edge invariants intact.

    The stored edge already points  edge.source_node_id → edge.target_node_id
    in the graph (i.e. ancestor → descendant).  When we prepend it to
    a backward-traversal path whose current start is edge.target_node_id,
    the invariant ``edges[i].source_node_id == nodes[i].id`` is
    preserved.
    """
    new_nodes = [ancestor_node] + list(path.nodes)
    new_edges = [edge] + list(path.edges)
    return LineagePath(nodes=new_nodes, edges=new_edges)


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

_DEFAULT_MAX_HOPS = 20


def trace_backward(
    graph: LineageGraph,
    start_node_id: str,
    *,
    max_hops: int = _DEFAULT_MAX_HOPS,
    edge_types: Optional[Collection[EdgeType]] = None,
    node_filter: Optional[Callable[[LineageNode], bool]] = None,
) -> TraversalResult:
    """
    Trace all upstream (ancestor) paths from ``start_node_id``.

    Starting from the given node, follows incoming edges recursively
    to discover every data source that contributes to it, up to
    ``max_hops`` hops away.

    Parameters
    ----------
    graph : LineageGraph
        The graph to traverse.  Must already contain ``start_node_id``.
    start_node_id : str
        Id of the node to start from.  The returned paths all end at
        this node (``path.end_node.id == start_node_id``).
    max_hops : int
        Maximum number of edge hops per path before the path is
        classified as truncated.  Default 20.  Set to a low value
        (e.g. 3) for performance when only nearby ancestors matter.
    edge_types : collection of EdgeType, optional
        If given, only edges whose ``edge_type`` is in this collection
        are followed.  E.g. pass ``{EdgeType.DATA_FLOW}`` to skip
        LOOKUP / JOIN edges.
    node_filter : callable, optional
        ``node_filter(node) → bool``.  If provided, a next-hop node
        is only added to the BFS frontier when the callable returns
        True.  Useful to prune traversal to specific node types
        (e.g. only SOURCE_TABLE nodes).

    Returns
    -------
    TraversalResult
        ``result.paths`` — complete upstream paths, shortest first.
        Each path's ``start_node`` is the furthest discovered ancestor;
        its ``end_node`` is ``start_node_id``'s node.

    Example
    -------
    ::

        result = trace_backward(graph, "job1:target_table:out1.amount")
        for path in result.paths:
            print(path.describe())
        if result.has_cycles:
            print("Cycles:", result.cycles_detected)
    """
    if max_hops < 1:
        raise ValueError(f"max_hops must be >= 1, got {max_hops}")
    if not isinstance(graph, LineageGraph):
        raise TypeError(f"graph must be a LineageGraph, got {type(graph).__name__}")
    if not start_node_id:
        raise ValueError("start_node_id must be a non-empty string")
    if edge_types is not None and not all(isinstance(et, EdgeType) for et in edge_types):
        raise TypeError("edge_types must contain only EdgeType members")

    return _bfs(
        graph=graph,
        start_node_id=start_node_id,
        direction="backward",
        max_hops=max_hops,
        edge_types=edge_types,
        node_filter=node_filter,
    )


def trace_forward(
    graph: LineageGraph,
    start_node_id: str,
    *,
    max_hops: int = _DEFAULT_MAX_HOPS,
    edge_types: Optional[Collection[EdgeType]] = None,
    node_filter: Optional[Callable[[LineageNode], bool]] = None,
) -> TraversalResult:
    """
    Trace all downstream (descendant) paths from ``start_node_id``.

    Starting from the given node, follows outgoing edges recursively
    to discover every downstream target, transformation, and lookup
    that depends on it, up to ``max_hops`` hops away.

    Parameters
    ----------
    graph : LineageGraph
        The graph to traverse.  Must already contain ``start_node_id``.
    start_node_id : str
        Id of the node to start from.  The returned paths all begin at
        this node (``path.start_node.id == start_node_id``).
    max_hops : int
        Maximum number of edge hops per path before the path is
        classified as truncated.  Default 20.
    edge_types : collection of EdgeType, optional
        If given, only edges whose ``edge_type`` is in this collection
        are followed.
    node_filter : callable, optional
        ``node_filter(node) → bool``.  Only next-hop nodes for which
        the callable returns True are explored.

    Returns
    -------
    TraversalResult
        ``result.paths`` — complete downstream paths, shortest first.
        Each path's ``start_node`` is ``start_node_id``'s node; its
        ``end_node`` is the furthest downstream node reached.

    Example
    -------
    ::

        result = trace_forward(graph, "job1:source_table:customers.id")
        for path in result.paths:
            print(path.describe())
    """
    if max_hops < 1:
        raise ValueError(f"max_hops must be >= 1, got {max_hops}")
    if not isinstance(graph, LineageGraph):
        raise TypeError(f"graph must be a LineageGraph, got {type(graph).__name__}")
    if not start_node_id:
        raise ValueError("start_node_id must be a non-empty string")
    if edge_types is not None and not all(isinstance(et, EdgeType) for et in edge_types):
        raise TypeError("edge_types must contain only EdgeType members")

    return _bfs(
        graph=graph,
        start_node_id=start_node_id,
        direction="forward",
        max_hops=max_hops,
        edge_types=edge_types,
        node_filter=node_filter,
    )


def find_paths_between(
    graph: LineageGraph,
    source_id: str,
    target_id: str,
    *,
    max_hops: int = _DEFAULT_MAX_HOPS,
    edge_types: Optional[Collection[EdgeType]] = None,
) -> list[LineagePath]:
    """
    Return all paths from ``source_id`` to ``target_id``.

    Performs a forward BFS from ``source_id`` and keeps only those
    complete paths whose ``end_node.id == target_id``.

    Parameters
    ----------
    graph : LineageGraph
    source_id : str
        Starting node id.
    target_id : str
        Ending node id.
    max_hops : int
        Per-path hop limit passed to the underlying BFS.
    edge_types : collection of EdgeType, optional
        Restrict which edge types are followed.

    Returns
    -------
    list[LineagePath]
        All paths from source to target, shortest-first.
        Empty list if no path exists within ``max_hops``.

    Raises
    ------
    ValueError
        If ``source_id`` or ``target_id`` is not in the graph.
    """
    if not graph.has_node(source_id):
        raise ValueError(f"source_id {source_id!r} not found in graph")
    if not graph.has_node(target_id):
        raise ValueError(f"target_id {target_id!r} not found in graph")

    result = trace_forward(
        graph,
        source_id,
        max_hops=max_hops,
        edge_types=edge_types,
    )

    # Keep only paths that end at the requested target
    matched = [p for p in result.paths if p.end_node.id == target_id]
    # Also check truncated paths (they may still pass through target)
    matched += [
        p for p in result.truncated_paths
        if any(n.id == target_id for n in p.nodes)
    ]
    matched.sort(key=lambda p: p.hop_count)
    return matched
