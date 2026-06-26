"""
app.lineage
===========
Pure, framework-independent domain model for column/table-level data
lineage.

This package has no dependency on Streamlit, on app.ui.*, or on
app.parser.* — it only defines the *shape* of lineage data (nodes,
edges, graphs, and traced paths) so that a future builder module
(translating ColumnMapping / parser output into these models), a
future traversal module (forward/backward multi-hop impact analysis),
and a future UI layer can all be implemented against one stable
contract.

See app/lineage/lineage_model.py for the implementation.
"""

from app.lineage.lineage_model import (
    NodeType,
    EdgeType,
    LineageNode,
    LineageEdge,
    LineageGraph,
    LineagePath,
)
from app.lineage.lineage_graph_builder import (
    build_graph,
    build_graphs_for_jobs,
    merge_job_graphs,
)
from app.lineage.lineage_traversal import (
    TraversalResult,
    TraversalStats,
    trace_backward,
    trace_forward,
    find_paths_between,
)

__all__ = [
    "NodeType",
    "EdgeType",
    "LineageNode",
    "LineageEdge",
    "LineageGraph",
    "LineagePath",
    "build_graph",
    "build_graphs_for_jobs",
    "merge_job_graphs",
    "TraversalResult",
    "TraversalStats",
    "trace_backward",
    "trace_forward",
    "find_paths_between",
]
