"""
repository_lineage_index.py
============================
Builds a unified, repository-wide lineage graph by:

  1. Parsing every job's ColumnMappings and MappingRuleDetails.
  2. Building a per-job LineageGraph via ``lineage_graph_builder.build_graph()``.
  3. Merging all per-job graphs into one combined graph via
     ``LineageGraph.merge()``.
  4. Adding cross-job **bridge edges** between nodes that share the same
     ``database.schema.table`` physical identity, so that a target written
     by Job A is automatically linked to the source read by Job B when they
     refer to the same physical table.

Cross-job identity key
-----------------------
The canonical key is formed from the node's first-class fields::

    "<database>.<schema>.<table>"   (all lowercase, empty segments omitted)

This matches the ``PhysicalTableRef.physical_key`` suffix (without the
db_type prefix), giving stable cross-technology matching when two jobs
connect to the same table via different drivers.

Public API
----------
::

    build_repository_index(
        jobs            : list[dict],
        *,
        progress_cb     : Callable[[int, int, str], None] | None = None,
    ) -> RepositoryLineageIndex

``RepositoryLineageIndex`` exposes:

    .graph              LineageGraph   — the fully merged + bridged graph
    .job_graphs         dict[str, LineageGraph]
    .physical_index     dict[str, list[str]]  — identity_key → [node_id, …]
    .bridge_edges       list[LineageEdge]      — cross-job DATA_FLOW edges added
    .stats              IndexStats

    .nodes_for_table(table, schema="", database="") → list[LineageNode]
    .jobs_for_table(table, schema="", database="")  → list[str]
    .downstream_jobs(job_name)  → list[str]
    .upstream_jobs(job_name)    → list[str]
    .all_tables()               → list[str]   unique table names across all jobs
    .summary()                  → dict        lightweight stats dict

No Streamlit dependency — this module is pure Python.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.lineage.lineage_graph_builder import build_graph
from app.lineage.lineage_model import (
    EdgeType,
    LineageEdge,
    LineageGraph,
    LineageNode,
    NodeType,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _dst_key(node: LineageNode) -> str:
    """
    Compute the database.schema.table identity key for *node*.

    Rules (all parts lowercased, empty parts omitted):
      - Prefer the first-class ``database``, ``schema``, ``table`` fields.
      - Fall back to ``metadata["table"]`` when ``node.table`` is blank.
      - Returns ``""`` when nothing can be determined (e.g. COMPONENT nodes).
    """
    tbl = node.table or node.metadata.get("table", "")
    if not tbl:
        return ""

    parts: list[str] = []
    if node.database:
        parts.append(node.database.lower())
    if node.schema:
        parts.append(node.schema.lower())
    parts.append(tbl.lower())
    return ".".join(parts)


def _load_job_mappings(job: dict):
    """
    Load (mappings, rule_details) for *job* without Streamlit side-effects.

    Uses the same underlying parser as ``column_mapping_service`` but
    bypasses all ``st.*`` debug calls so it is safe to call in batch.
    """
    from app.ui.column_mapping_dto import from_parser_row, from_rule_row

    mappings: list = []
    rule_details: list = []

    file_path = job.get("file_path", "")
    if not file_path:
        return mappings, rule_details

    import os
    item_path = os.path.abspath(file_path)
    if not os.path.isfile(item_path):
        return mappings, rule_details

    try:
        from app.cache.cache_manager import CacheManager as _CM
        _job_data = _CM().load_or_parse(item_path)
        for r in (_job_data.get("column_mappings") or []):
            try:
                mappings.append(from_parser_row(r))
            except Exception:
                pass
        for r in (_job_data.get("mapping_rules") or []):
            try:
                rule_details.append(from_rule_row(r))
            except Exception:
                pass
    except Exception as exc:
        logger.warning("repository_lineage_index: parse failed for %r: %s", file_path, exc)

    return mappings, rule_details


def _load_component_physical_map(job: dict) -> Optional[dict]:
    """
    Build the component→PhysicalTableRef map for *job* when possible.
    Returns None on failure (non-fatal).
    """
    try:
        from app.cache.cache_manager import CacheManager as _CM
        from app.parser.source_target_extractor import build_component_physical_map
        import os

        file_path = job.get("file_path", "")
        if not file_path:
            return None
        item_path = os.path.abspath(file_path)
        if not os.path.isfile(item_path):
            return None

        _job_data  = _CM().load_or_parse(item_path)
        components = _job_data.get("components") or []
        return build_component_physical_map(components)
    except Exception as exc:
        logger.debug("repository_lineage_index: physical map failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IndexStats:
    total_jobs:       int   = 0
    jobs_parsed:      int   = 0
    jobs_empty:       int   = 0
    total_nodes:      int   = 0
    total_edges:      int   = 0
    bridge_edges:     int   = 0
    unique_tables:    int   = 0
    cross_job_links:  int   = 0   # distinct identity keys that span ≥2 jobs
    elapsed_seconds:  float = 0.0

    def summary(self) -> str:
        return (
            f"jobs={self.jobs_parsed}/{self.total_jobs}  "
            f"nodes={self.total_nodes}  edges={self.total_edges}  "
            f"bridges={self.bridge_edges}  tables={self.unique_tables}  "
            f"cross_job_links={self.cross_job_links}  "
            f"elapsed={self.elapsed_seconds:.3f}s"
        )


@dataclass
class RepositoryLineageIndex:
    """
    Repository-wide lineage index.

    Attributes
    ----------
    graph           : LineageGraph
        Merged graph containing every node/edge from all jobs plus
        cross-job bridge edges.
    job_graphs      : dict[str, LineageGraph]
        Individual per-job graphs (pre-merge), keyed by job_name.
    physical_index  : dict[str, list[str]]
        Maps ``database.schema.table`` identity key → list of node ids that
        share that physical table (may span multiple jobs).
    bridge_edges    : list[LineageEdge]
        The DATA_FLOW edges added during cross-job stitching.
    stats           : IndexStats
    """

    graph:          LineageGraph                    = field(default_factory=LineageGraph)
    job_graphs:     dict[str, LineageGraph]         = field(default_factory=dict)
    physical_index: dict[str, list[str]]            = field(default_factory=dict)
    bridge_edges:   list[LineageEdge]               = field(default_factory=list)
    stats:          IndexStats                      = field(default_factory=IndexStats)

    # ── Convenience accessors ─────────────────────────────────────────────────

    def nodes_for_table(
        self,
        table: str,
        schema: str = "",
        database: str = "",
    ) -> list[LineageNode]:
        """Return all nodes whose physical identity matches (table, schema, database)."""
        parts: list[str] = []
        if database:
            parts.append(database.lower())
        if schema:
            parts.append(schema.lower())
        parts.append(table.lower())
        key = ".".join(parts)

        # Try exact key first; fall back to table-only suffix search
        node_ids = self.physical_index.get(key, [])
        if not node_ids and len(parts) > 1:
            suffix = table.lower()
            node_ids = [
                nid for k, ids in self.physical_index.items()
                if k == suffix or k.endswith(f".{suffix}")
                for nid in ids
            ]

        return [n for nid in node_ids if (n := self.graph.get_node(nid)) is not None]

    def jobs_for_table(
        self,
        table: str,
        schema: str = "",
        database: str = "",
    ) -> list[str]:
        """Return distinct job names that touch the given physical table."""
        nodes = self.nodes_for_table(table, schema, database)
        return sorted({n.job_name for n in nodes if n.job_name})

    def downstream_jobs(self, job_name: str) -> list[str]:
        """
        Return jobs that read a table written by *job_name*.

        A job B is downstream of A when A writes a target table that B reads
        as a source (connected via a bridge edge).
        """
        downstream: set[str] = set()
        for edge in self.bridge_edges:
            src = self.graph.get_node(edge.source_node_id)
            tgt = self.graph.get_node(edge.target_node_id)
            if src and tgt and src.job_name == job_name and tgt.job_name != job_name:
                downstream.add(tgt.job_name)
        return sorted(downstream)

    def upstream_jobs(self, job_name: str) -> list[str]:
        """
        Return jobs that write a table read by *job_name*.
        """
        upstream: set[str] = set()
        for edge in self.bridge_edges:
            src = self.graph.get_node(edge.source_node_id)
            tgt = self.graph.get_node(edge.target_node_id)
            if src and tgt and tgt.job_name == job_name and src.job_name != job_name:
                upstream.add(src.job_name)
        return sorted(upstream)

    def all_tables(self) -> list[str]:
        """Return a sorted list of unique table names across all jobs."""
        tables: set[str] = set()
        for node in self.graph.nodes:
            t = node.table or node.metadata.get("table", "")
            if t and node.node_type in (NodeType.SOURCE_TABLE, NodeType.TARGET_TABLE):
                tables.add(t.upper())
        return sorted(tables)

    def summary(self) -> dict:
        return {
            "total_jobs":      self.stats.total_jobs,
            "jobs_parsed":     self.stats.jobs_parsed,
            "total_nodes":     self.stats.total_nodes,
            "total_edges":     self.stats.total_edges,
            "bridge_edges":    self.stats.bridge_edges,
            "unique_tables":   self.stats.unique_tables,
            "cross_job_links": self.stats.cross_job_links,
            "elapsed_seconds": round(self.stats.elapsed_seconds, 3),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1: per-job graph construction
# ─────────────────────────────────────────────────────────────────────────────

def _build_per_job_graphs(
    jobs: list[dict],
    progress_cb: Optional[Callable[[int, int, str], None]],
) -> tuple[dict[str, LineageGraph], int]:
    """
    Build one LineageGraph per job.

    Returns (job_graphs, jobs_parsed_count).
    """
    job_graphs: dict[str, LineageGraph] = {}
    jobs_parsed = 0

    for i, job in enumerate(jobs):
        job_name = (
            job.get("job_data", {}).get("job_name")
            or job.get("job_name")
            or f"job_{i}"
        )
        if progress_cb:
            progress_cb(i, len(jobs), f"Parsing {job_name}")

        mappings, rule_details = _load_job_mappings(job)
        if not mappings and not rule_details:
            logger.debug("repository_lineage_index: no mappings for %r — skipping", job_name)
            job_graphs[job_name] = LineageGraph()
            continue

        comp_map = _load_component_physical_map(job)
        graph = build_graph(
            mappings=mappings,
            rule_details=rule_details,
            job_name=job_name,
            component_physical_map=comp_map,
        )
        job_graphs[job_name] = graph
        jobs_parsed += 1
        logger.info(
            "repository_lineage_index: built graph for %r — %d nodes, %d edges",
            job_name, graph.node_count, graph.edge_count,
        )

    return job_graphs, jobs_parsed


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: merge all per-job graphs
# ─────────────────────────────────────────────────────────────────────────────

def _merge_graphs(job_graphs: dict[str, LineageGraph]) -> LineageGraph:
    """Merge all per-job graphs into one combined graph."""
    combined = LineageGraph()
    for job_name, g in job_graphs.items():
        combined = combined.merge(g)
        logger.debug("repository_lineage_index: merged %r → %r", job_name, combined)
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: build physical identity index (database.schema.table)
# ─────────────────────────────────────────────────────────────────────────────

def _build_physical_index(
    combined: LineageGraph,
) -> dict[str, list[str]]:
    """
    Build a mapping: ``database.schema.table`` → [node_id, …].

    Only SOURCE_TABLE and TARGET_TABLE nodes participate; COMPONENT and
    LOOKUP_TABLE nodes are excluded (they are transforms, not physical tables).
    """
    index: dict[str, list[str]] = defaultdict(list)

    for node in combined.nodes:
        if node.node_type not in (NodeType.SOURCE_TABLE, NodeType.TARGET_TABLE):
            continue
        key = _dst_key(node)
        if key:
            index[key].append(node.id)

    return dict(index)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: add cross-job bridge edges
# ─────────────────────────────────────────────────────────────────────────────

def _add_bridge_edges(
    combined: LineageGraph,
    physical_index: dict[str, list[str]],
) -> list[LineageEdge]:
    """
    For every physical identity key that maps to ≥2 nodes from different jobs,
    add a directed DATA_FLOW bridge edge from each TARGET_TABLE node to every
    SOURCE_TABLE node that shares the same identity (and belongs to a different
    job).

    Direction: writer_job.TARGET_TABLE → reader_job.SOURCE_TABLE
    This models the real-world flow: Job A writes a table, Job B reads it.

    Returns the list of bridge edges added.
    """
    bridge_edges: list[LineageEdge] = []

    for key, node_ids in physical_index.items():
        if len(node_ids) < 2:
            continue

        nodes = [combined.get_node(nid) for nid in node_ids]
        nodes = [n for n in nodes if n is not None]

        # Partition into writers (TARGET_TABLE) and readers (SOURCE_TABLE)
        writers  = [n for n in nodes if n.node_type == NodeType.TARGET_TABLE]
        readers  = [n for n in nodes if n.node_type == NodeType.SOURCE_TABLE]

        for writer in writers:
            for reader in readers:
                # Skip same-job links — intra-job flow is already in the graph
                if writer.job_name == reader.job_name:
                    continue

                edge = LineageEdge(
                    source_node_id=writer.id,
                    target_node_id=reader.id,
                    edge_type=EdgeType.DATA_FLOW,
                    job_name="",           # spans multiple jobs
                    rule="Cross-Job Bridge",
                    rule_type="bridge",
                    metadata={
                        "physical_key":   key,
                        "source_job":     writer.job_name,
                        "target_job":     reader.job_name,
                        "bridge":         True,
                    },
                )
                try:
                    combined.add_edge(edge)
                    bridge_edges.append(edge)
                    logger.debug(
                        "repository_lineage_index: bridge %r → %r via key=%r",
                        writer.job_name, reader.job_name, key,
                    )
                except ValueError as exc:
                    logger.debug("repository_lineage_index: bridge edge skipped: %s", exc)

    return bridge_edges


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def build_repository_index(
    jobs: list[dict],
    *,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> RepositoryLineageIndex:
    """
    Build a repository-wide lineage index across all jobs.

    Parameters
    ----------
    jobs : list[dict]
        Job descriptors as found in ``st.session_state["last_analysis_jobs"]``.
        Each dict is expected to have at minimum a ``"file_path"`` key and
        either ``"job_data": {"job_name": ...}`` or a top-level ``"job_name"``.
    progress_cb : callable, optional
        Called as ``progress_cb(current, total, label)`` during parsing so
        callers can display a progress bar.  Not required.

    Returns
    -------
    RepositoryLineageIndex
        A fully built index with:
        - Per-job graphs in ``.job_graphs``
        - Merged graph in ``.graph`` (with bridge edges inserted)
        - Physical identity index in ``.physical_index``
        - Cross-job bridge edges in ``.bridge_edges``
        - Build statistics in ``.stats``

    Algorithm
    ---------
    Phase 1  Parse every job → per-job ``LineageGraph``
    Phase 2  Merge all per-job graphs into one combined ``LineageGraph``
    Phase 3  Build ``database.schema.table`` physical identity index
    Phase 4  Add cross-job bridge edges (TARGET→SOURCE for shared tables)
    """
    t0 = time.perf_counter()
    stats = IndexStats(total_jobs=len(jobs))

    # ── Phase 1 ───────────────────────────────────────────────────────────────
    if progress_cb:
        progress_cb(0, len(jobs), "Building per-job graphs…")
    job_graphs, jobs_parsed = _build_per_job_graphs(jobs, progress_cb)
    stats.jobs_parsed = jobs_parsed
    stats.jobs_empty  = len(jobs) - jobs_parsed

    # ── Phase 2 ───────────────────────────────────────────────────────────────
    if progress_cb:
        progress_cb(len(jobs), len(jobs), "Merging graphs…")
    combined = _merge_graphs(job_graphs)

    # ── Phase 3 ───────────────────────────────────────────────────────────────
    physical_index = _build_physical_index(combined)
    stats.unique_tables = len(physical_index)
    stats.cross_job_links = sum(
        1 for ids in physical_index.values()
        if len({combined.get_node(nid).job_name for nid in ids if combined.get_node(nid)}) > 1
    )

    # ── Phase 4 ───────────────────────────────────────────────────────────────
    bridge_edges = _add_bridge_edges(combined, physical_index)

    # ── Final stats ───────────────────────────────────────────────────────────
    stats.total_nodes     = combined.node_count
    stats.total_edges     = combined.edge_count
    stats.bridge_edges    = len(bridge_edges)
    stats.elapsed_seconds = time.perf_counter() - t0

    logger.info("repository_lineage_index: %s", stats.summary())

    return RepositoryLineageIndex(
        graph=combined,
        job_graphs=job_graphs,
        physical_index=dict(physical_index),
        bridge_edges=bridge_edges,
        stats=stats,
    )
