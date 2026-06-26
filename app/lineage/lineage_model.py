"""
lineage_model.py
================
Core domain model for the Talend lineage graph.

Classes
-------
NodeType        Enum of node roles (SOURCE_TABLE, TARGET_TABLE, COMPONENT, LOOKUP_TABLE)
EdgeType        Enum of edge semantics (DATA_FLOW, JOIN, LOOKUP)
LineageNode     A vertex in the lineage graph, carrying physical-table metadata
LineageEdge     A directed edge between two LineageNode instances
LineageGraph    Container for nodes and edges with merge / query helpers

LineageNode — physical-table metadata fields (Phase 3)
-------------------------------------------------------
Every node now exposes six first-class attributes in addition to the
pre-existing ``system_type`` / ``physical_identity`` / ``metadata`` fields:

    system_type     : str   Technology label (e.g. "MySQL", "Snowflake", "File")
                            Already existed; now also populated from PhysicalTableRef.
    database        : str   Database / catalog name  (e.g. "customers_db")
    schema          : str   Schema / owner name      (e.g. "dbo", "HR")
    table           : str   Physical table name      (e.g. "CUSTOMERS")
    component_name  : str   Talend unique component name (e.g. "tMysqlInput_1")
    component_type  : str   Talend component type    (e.g. "tMysqlInput")

These are populated by ``lineage_graph_builder`` from the
``PhysicalTableRef`` returned by ``source_target_extractor``.
All six fields default to ``""`` so that existing code that creates
``LineageNode`` without them is unaffected.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Optional
from defusedxml import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Enumerations
# ────────────────────────────────────────────────────────────────────────────

class NodeType(str, Enum):
    SOURCE_TABLE  = "SOURCE_TABLE"
    TARGET_TABLE  = "TARGET_TABLE"
    COMPONENT     = "COMPONENT"
    LOOKUP_TABLE  = "LOOKUP_TABLE"


class EdgeType(str, Enum):
    DATA_FLOW = "DATA_FLOW"
    JOIN      = "JOIN"
    LOOKUP    = "LOOKUP"


# ────────────────────────────────────────────────────────────────────────────
# LineageNode
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class LineageNode:
    """
    A vertex in the lineage graph.

    Core identity fields
    --------------------
    id                : str        Unique node identifier (scoped per job+type+table+column)
    node_type         : NodeType   Role of this node in the graph
    label             : str        Human-readable display label
    job_name          : str        Talend job this node belongs to
    physical_identity : str        Normalised cross-job identity key (e.g. "mysql:customers")

    Physical-table metadata (Phase 3)
    ----------------------------------
    system_type       : str   Technology label  — "MySQL", "Snowflake", "File", …
    database          : str   Database / catalog name  (e.g. "customers_db")
    schema            : str   Schema / owner name      (e.g. "dbo", "HR")
    table             : str   Physical table name      (e.g. "CUSTOMERS")
    component_name    : str   Talend unique component name (e.g. "tMysqlInput_1")
    component_type    : str   Talend component type    (e.g. "tMysqlInput")

    Arbitrary extras
    ----------------
    metadata          : dict  Catch-all bag for expressions, filters, joins, etc.
                              The six physical fields above are *also* mirrored here
                              as ``"system_type"``, ``"database"``, ``"schema"``,
                              ``"table"``, ``"component_name"``, ``"component_type"``
                              for backwards-compatibility with callers that read
                              from ``node.metadata``.
    """

    # ── Core identity ────────────────────────────────────────────────────────
    id:                str      = ""
    node_type:         NodeType = NodeType.SOURCE_TABLE
    label:             str      = ""
    job_name:          str      = ""
    physical_identity: str      = ""

    # ── Physical-table metadata (Phase 3 — first-class fields) ───────────────
    system_type:    str = ""   # e.g. "MySQL", "Snowflake", "File"
    database:       str = ""   # e.g. "customers_db"
    schema:         str = ""   # e.g. "dbo", "HR"
    table:          str = ""   # e.g. "CUSTOMERS"
    component_name: str = ""   # e.g. "tMysqlInput_1"
    component_type: str = ""   # e.g. "tMysqlInput"

    # ── Arbitrary extras ─────────────────────────────────────────────────────
    metadata: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Post-init: mirror the six physical fields into metadata so that
    # callers reading node.metadata["database"] etc. still work.
    # ------------------------------------------------------------------
    def __post_init__(self) -> None:
        # Ensure the six first-class fields are always reflected in metadata.
        # Caller-supplied metadata values take precedence where they conflict.
        physical_mirror: dict[str, str] = {
            "system_type":    self.system_type,
            "database":       self.database,
            "schema":         self.schema,
            "table":          self.table,
            "component_name": self.component_name,
            "component_type": self.component_type,
        }
        for key, value in physical_mirror.items():
            if value and key not in self.metadata:
                self.metadata[key] = value

    # ------------------------------------------------------------------
    # Merge support
    # ------------------------------------------------------------------
    def merged_with(self, other: "LineageNode") -> "LineageNode":
        """
        Return a new node that combines ``self`` with ``other``.

        Rules:
          • First non-empty value wins for scalar string fields.
          • ``metadata`` dicts are shallow-merged (other wins on key clash).
          • The six physical fields are re-derived from the merged metadata
            so they stay in sync.
        """
        if self.id != other.id:
            raise ValueError(
                f"Cannot merge nodes with different ids: {self.id!r} vs {other.id!r}"
            )

        def _first(*values: str) -> str:
            return next((v for v in values if v), "")

        merged_meta = {**self.metadata, **other.metadata}

        # The six physical fields are resolved with "other wins" precedence,
        # but merged_meta may still carry stale mirrored values from
        # whichever side contributed metadata first. Force the mirror back
        # in sync with the resolved fields so node.metadata never disagrees
        # with the node's own first-class attributes (node identity bug).
        resolved_physical = {
            "system_type":    _first(other.system_type,    self.system_type),
            "database":       _first(other.database,       self.database),
            "schema":         _first(other.schema,         self.schema),
            "table":          _first(other.table,          self.table),
            "component_name": _first(other.component_name, self.component_name),
            "component_type": _first(other.component_type, self.component_type),
        }
        for key, value in resolved_physical.items():
            if value:
                merged_meta[key] = value

        node = LineageNode(
            id=self.id,
            node_type=self.node_type,
            label=_first(self.label, other.label),
            job_name=_first(self.job_name, other.job_name),
            physical_identity=_first(self.physical_identity, other.physical_identity),
            # Physical fields: prefer other (more recent resolution wins)
            system_type=resolved_physical["system_type"],
            database=   resolved_physical["database"],
            schema=     resolved_physical["schema"],
            table=      resolved_physical["table"],
            component_name=resolved_physical["component_name"],
            component_type=resolved_physical["component_type"],
            metadata=merged_meta,
        )
        return node

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------
    @property
    def qualified_table(self) -> str:
        """
        Dot-separated physical address, e.g. ``"MySQL.HR.EMPLOYEES"``.
        Omits empty segments.
        """
        parts = [
            self.system_type.upper() if self.system_type else "",
            self.database.upper() if self.database else "",
            self.schema.upper() if self.schema else "",
            self.table.upper() if self.table else "",
        ]
        return ".".join(p for p in parts if p)

    def __repr__(self) -> str:
        return (
            f"LineageNode(id={self.id!r}, type={self.node_type.value}, "
            f"label={self.label!r}, system={self.system_type!r}, "
            f"db={self.database!r}, schema={self.schema!r}, table={self.table!r}, "
            f"component={self.component_name!r}/{self.component_type!r})"
        )


# ────────────────────────────────────────────────────────────────────────────
# LineageEdge
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class LineageEdge:
    """
    A directed edge between two LineageNode instances.

    Mandatory fields
    ----------------
    source_node_id : str      id of the source LineageNode
    target_node_id : str      id of the target LineageNode
    edge_type      : EdgeType Semantic type of the edge

    Optional fields
    ---------------
    job_name       : str      Talend job this edge belongs to
    rule           : str      Mapping rule label
    rule_type      : str      Rule category (e.g. "join", "lookup", "direct")
    expression     : str      Raw tMap expression
    source_column  : str      Source column name
    target_column  : str      Target column name
    metadata       : dict     Catch-all extras (join_type, match_mode, phase, …)
    """

    source_node_id: str      = ""
    target_node_id: str      = ""
    edge_type:      EdgeType = EdgeType.DATA_FLOW

    job_name:      str  = ""
    rule:          str  = ""
    rule_type:     str  = ""
    expression:    str  = ""
    source_column: str  = ""
    target_column: str  = ""
    metadata:      dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_node_id or not self.target_node_id:
            raise ValueError(
                "LineageEdge requires non-empty source_node_id and target_node_id. "
                f"Got source={self.source_node_id!r}, target={self.target_node_id!r}"
            )

    @property
    def id(self) -> str:
        """
        Synthetic edge identifier (not stored, derived on demand).

        Includes source_column/target_column so that two genuinely
        distinct column-level mappings sharing the same component pair
        and edge_type (e.g. two different tMap output columns) are not
        collapsed into a single edge on add_edge(); only edges that are
        truly identical across every distinguishing field collide.
        """
        return (
            f"{self.source_node_id}→{self.target_node_id}"
            f"[{self.edge_type.value}:{self.source_column}:{self.target_column}]"
        )

    def __repr__(self) -> str:
        return (
            f"LineageEdge({self.source_node_id!r} →[{self.edge_type.value}]→ "
            f"{self.target_node_id!r}, rule={self.rule!r})"
        )


# ────────────────────────────────────────────────────────────────────────────
# LineageGraph
# ────────────────────────────────────────────────────────────────────────────

class LineageGraph:
    """
    Container for LineageNode and LineageEdge instances.

    Nodes are stored in insertion order, deduplicated by id.
    When a node with the same id is added twice, the two instances are
    merged via ``LineageNode.merged_with()``.

    Edges are stored in insertion order, deduplicated by their synthetic
    ``id`` property (source→target[type]).  Duplicate edges are silently
    dropped.
    """

    def __init__(
        self,
        nodes: Optional[Iterable["LineageNode"]] = None,
        edges: Optional[Iterable["LineageEdge"]] = None,
    ) -> None:
        self._nodes: dict[str, LineageNode] = {}
        self._edges: dict[str, LineageEdge] = {}
        # Adjacency indexes: node_id -> list of edge ids. Avoids an O(E)
        # scan over all edges on every edges_from()/edges_to() call, which
        # made BFS traversal (_bfs in lineage_traversal.py) O(V*E) on large
        # repository-wide graphs.
        self._edges_from_index: dict[str, list[str]] = {}
        self._edges_to_index:   dict[str, list[str]] = {}
        # physical_identity -> node ids, rebuilt lazily on add_node since
        # merged_with() can change a node's physical_identity in place of
        # the original add. None means "stale, rebuild on next lookup".
        self._physical_identity_index: Optional[dict[str, list[str]]] = None

        for node in nodes or []:
            self.add_node(node)
        for edge in edges or []:
            self.add_edge(edge)

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_node(self, node: LineageNode) -> LineageNode:
        """
        Add *node* to the graph.

        If a node with the same ``id`` already exists, the two are merged
        and the merged node replaces the original.  The merged node is
        returned in both cases.
        """
        existing = self._nodes.get(node.id)
        if existing is not None:
            merged = existing.merged_with(node)
            self._nodes[node.id] = merged
            self._physical_identity_index = None  # stale: merge may change identity
            return merged
        self._nodes[node.id] = node
        self._physical_identity_index = None  # stale: invalidate lazy index
        return node

    def get_node(self, node_id: str) -> Optional[LineageNode]:
        return self._nodes.get(node_id)

    @property
    def nodes(self) -> list[LineageNode]:
        return list(self._nodes.values())

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def find_nodes_by_type(self, node_type: NodeType) -> list[LineageNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def find_nodes_by_physical_identity(self, physical_identity: str) -> list[LineageNode]:
        """Return all nodes whose ``physical_identity`` matches *physical_identity*."""
        if self._physical_identity_index is None:
            index: dict[str, list[str]] = {}
            for n in self._nodes.values():
                if n.physical_identity:
                    index.setdefault(n.physical_identity, []).append(n.id)
            self._physical_identity_index = index
        return [
            self._nodes[nid]
            for nid in self._physical_identity_index.get(physical_identity, ())
        ]

    def find_nodes_by_system_type(self, system_type: str) -> list[LineageNode]:
        """Return all nodes whose ``system_type`` matches *system_type* (case-insensitive)."""
        target = system_type.lower()
        return [n for n in self._nodes.values() if n.system_type.lower() == target]

    def find_nodes_by_table(
        self,
        table: str,
        schema: str = "",
        database: str = "",
    ) -> list[LineageNode]:
        """
        Return nodes matching *table* (case-insensitive), optionally
        narrowing by *schema* and/or *database*.
        """
        table_lower    = table.lower()
        schema_lower   = schema.lower()
        database_lower = database.lower()
        results = []
        for n in self._nodes.values():
            if n.table.lower() != table_lower:
                continue
            if schema_lower and n.schema.lower() != schema_lower:
                continue
            if database_lower and n.database.lower() != database_lower:
                continue
            results.append(n)
        return results

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, edge: LineageEdge) -> LineageEdge:
        """
        Add *edge* to the graph.

        Raises ``ValueError`` if either endpoint node is not present.
        Silently deduplicates edges with the same synthetic id.
        """
        if edge.source_node_id not in self._nodes:
            raise ValueError(
                f"Source node {edge.source_node_id!r} not found in graph"
            )
        if edge.target_node_id not in self._nodes:
            raise ValueError(
                f"Target node {edge.target_node_id!r} not found in graph"
            )
        if edge.id not in self._edges:
            self._edges[edge.id] = edge
            self._edges_from_index.setdefault(edge.source_node_id, []).append(edge.id)
            self._edges_to_index.setdefault(edge.target_node_id, []).append(edge.id)
        return self._edges[edge.id]

    @property
    def edges(self) -> list[LineageEdge]:
        return list(self._edges.values())

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    def edges_from(self, node_id: str) -> list[LineageEdge]:
        return [self._edges[eid] for eid in self._edges_from_index.get(node_id, ())]

    def edges_to(self, node_id: str) -> list[LineageEdge]:
        return [self._edges[eid] for eid in self._edges_to_index.get(node_id, ())]

    def outgoing_edges(self, node_id: str) -> list[LineageEdge]:
        """Return all edges whose source is node_id."""
        return self.edges_from(node_id)

    def incoming_edges(self, node_id: str) -> list[LineageEdge]:
        """Return all edges whose target is node_id."""
        return self.edges_to(node_id)

    def has_node(self, node_id: str) -> bool:
        """Return True if a node with node_id exists in the graph."""
        return node_id in self._nodes

    @property
    def is_empty(self) -> bool:
        """Return True if the graph has no nodes (and therefore no edges)."""
        return not self._nodes

    # ------------------------------------------------------------------
    # Graph operations
    # ------------------------------------------------------------------

    def merge(self, other: "LineageGraph") -> "LineageGraph":
        """
        Return a new LineageGraph that is the union of ``self`` and ``other``.

        Node conflicts are resolved by ``LineageNode.merged_with()``.
        Duplicate edges are silently dropped.
        """
        merged = LineageGraph()
        for node in self.nodes:
            merged.add_node(node)
        for node in other.nodes:
            merged.add_node(node)
        for edge in self.edges:
            try:
                merged.add_edge(edge)
            except ValueError as exc:
                logger.debug("merge: skipping edge from self: %s", exc)
        for edge in other.edges:
            try:
                merged.add_edge(edge)
            except ValueError as exc:
                logger.debug("merge: skipping edge from other: %s", exc)
        return merged

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary dict suitable for logging or display."""
        type_counts: dict[str, int] = {}
        for n in self._nodes.values():
            key = n.node_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        edge_counts: dict[str, int] = {}
        for e in self._edges.values():
            key = e.edge_type.value
            edge_counts[key] = edge_counts.get(key, 0) + 1

        systems: set[str] = {n.system_type for n in self._nodes.values() if n.system_type}

        return {
            "node_count":  self.node_count,
            "edge_count":  self.edge_count,
            "node_types":  type_counts,
            "edge_types":  edge_counts,
            "system_types": sorted(systems),
        }

    def statistics(self) -> dict[str, Any]:
        """
        Return a deeper statistics dict for dashboards: counts already
        in ``summary()`` plus per-job breakdown, fan-out/fan-in extremes,
        isolated nodes, and table/column coverage.
        """
        base = self.summary()

        jobs: dict[str, int] = {}
        tables: set[str] = set()
        for n in self._nodes.values():
            if n.job_name:
                jobs[n.job_name] = jobs.get(n.job_name, 0) + 1
            if n.table:
                tables.add(n.table)

        fan_out: dict[str, int] = {}
        fan_in:  dict[str, int] = {}
        for e in self._edges.values():
            fan_out[e.source_node_id] = fan_out.get(e.source_node_id, 0) + 1
            fan_in[e.target_node_id]  = fan_in.get(e.target_node_id, 0) + 1

        isolated = [
            nid for nid in self._nodes
            if nid not in fan_out and nid not in fan_in
        ]

        def _top(d: dict[str, int], n: int = 5) -> list[tuple[str, int]]:
            return sorted(d.items(), key=lambda kv: -kv[1])[:n]

        base.update({
            "job_count":            len(jobs),
            "nodes_per_job":        jobs,
            "distinct_tables":      len(tables),
            "isolated_node_count":  len(isolated),
            "isolated_node_ids":    isolated[:20],
            "top_fan_out":          _top(fan_out),
            "top_fan_in":           _top(fan_in),
            "avg_fan_out":          round(sum(fan_out.values()) / len(fan_out), 2) if fan_out else 0.0,
        })
        return base

    # ------------------------------------------------------------------
    # JSON export
    # ------------------------------------------------------------------

    @staticmethod
    def _node_to_dict(node: LineageNode) -> dict[str, Any]:
        return {
            "id":                node.id,
            "node_type":         node.node_type.value,
            "label":             node.label,
            "job_name":          node.job_name,
            "physical_identity": node.physical_identity,
            "system_type":       node.system_type,
            "database":          node.database,
            "schema":            node.schema,
            "table":             node.table,
            "component_name":    node.component_name,
            "component_type":    node.component_type,
            "metadata":          node.metadata,
        }

    @staticmethod
    def _edge_to_dict(edge: LineageEdge) -> dict[str, Any]:
        return {
            "id":              edge.id,
            "source_node_id":  edge.source_node_id,
            "target_node_id":  edge.target_node_id,
            "edge_type":       edge.edge_type.value,
            "job_name":        edge.job_name,
            "rule":            edge.rule,
            "rule_type":       edge.rule_type,
            "expression":      edge.expression,
            "source_column":   edge.source_column,
            "target_column":   edge.target_column,
            "metadata":        edge.metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        """
        Return a plain-dict (JSON-serialisable) representation of the
        graph: every node, every edge, and a ``metadata`` block (the
        same counts produced by ``summary()``).
        """
        return {
            "nodes":    [self._node_to_dict(n) for n in self.nodes],
            "edges":    [self._edge_to_dict(e) for e in self.edges],
            "metadata": self.summary(),
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """
        Serialise the graph to a JSON string with three top-level keys:

            "nodes"    - list of node objects (id, node_type, label,
                         job_name, physical_identity, the six physical
                         fields, and metadata)
            "edges"    - list of edge objects (id, source_node_id,
                         target_node_id, edge_type, job_name, rule,
                         rule_type, expression, source/target column,
                         and metadata)
            "metadata" - graph-level summary (node_count, edge_count,
                         node_types, edge_types, system_types)

        Pass ``indent=None`` for compact (single-line) output.
        """
        return json.dumps(self.to_dict(), indent=indent, default=str)

    # ------------------------------------------------------------------
    # GraphML export
    # ------------------------------------------------------------------

    # Node/edge dataclass fields exposed as typed GraphML <key>/<data>
    # attributes. "metadata" is flattened to a JSON string since GraphML's
    # primitive attribute types (string/int/double/boolean) have no
    # first-class dict support. Edge "uid" preserves LineageEdge.id (which
    # contains "→" and therefore cannot itself be used as an XML id).
    _GRAPHML_NODE_ATTRS = (
        "node_type", "label", "job_name", "physical_identity",
        "system_type", "database", "schema", "table",
        "component_name", "component_type", "metadata",
    )
    _GRAPHML_EDGE_ATTRS = (
        "uid", "edge_type", "job_name", "rule", "rule_type",
        "expression", "source_column", "target_column", "metadata",
    )

    def to_graphml(self) -> str:
        """
        Serialise the graph to a standard GraphML XML document.

        Exports exactly the nodes and the edges:
          • one ``<node>`` element per ``LineageNode``, id = ``node.id``
          • one ``<edge>`` element per ``LineageEdge``, with
            ``source``/``target`` set to the endpoint node ids
        Every dataclass field is declared as a typed ``<key>`` and
        emitted as ``<data>``; the catch-all ``metadata`` dict is
        flattened to a JSON string. Edge ids are synthetic and
        sequential (``e0``, ``e1``, …) — the natural
        ``LineageEdge.id`` (e.g. ``"a→b[DATA_FLOW]"``) is preserved as
        the ``uid`` data attribute since it is not a valid XML ``ID``.

        There is no graph-level metadata block in this format (GraphML
        has no first-class place for one) — use ``to_json()`` when the
        ``summary()`` block is also needed.
        """
        lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns '
            'http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        ]

        for attr in self._GRAPHML_NODE_ATTRS:
            lines.append(
                f'  <key id="n_{attr}" for="node" attr.name="{attr}" attr.type="string"/>'
            )
        for attr in self._GRAPHML_EDGE_ATTRS:
            lines.append(
                f'  <key id="e_{attr}" for="edge" attr.name="{attr}" attr.type="string"/>'
            )

        lines.append('  <graph id="G" edgedefault="directed">')

        for node in self.nodes:
            node_dict = self._node_to_dict(node)
            lines.append(f'    <node id={quoteattr(node.id)}>')
            for attr in self._GRAPHML_NODE_ATTRS:
                if attr == "metadata":
                    meta = node_dict.get("metadata") or {}
                    value = json.dumps(meta, default=str) if meta else ""
                else:
                    value = node_dict.get(attr, "")
                value = "" if value is None else str(value)
                if value:
                    lines.append(f'      <data key="n_{attr}">{escape(value)}</data>')
            lines.append('    </node>')

        for i, edge in enumerate(self.edges):
            edge_dict = self._edge_to_dict(edge)
            lines.append(
                f'    <edge id="e{i}" source={quoteattr(edge.source_node_id)} '
                f'target={quoteattr(edge.target_node_id)}>'
            )
            for attr in self._GRAPHML_EDGE_ATTRS:
                if attr == "uid":
                    value = edge_dict.get("id", "")
                elif attr == "metadata":
                    meta = edge_dict.get("metadata") or {}
                    value = json.dumps(meta, default=str) if meta else ""
                else:
                    value = edge_dict.get(attr, "")
                value = "" if value is None else str(value)
                if value:
                    lines.append(f'      <data key="e_{attr}">{escape(value)}</data>')
            lines.append('    </edge>')

        lines.append('  </graph>')
        lines.append('</graphml>')
        graphml_str = "\n".join(lines)

        try:
            ET.fromstring(graphml_str)
        except ET.ParseError as e:
            raise ValueError(f"Generated GraphML is not well-formed XML: {e}") from e

        return graphml_str

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    def to_csv(self) -> str:
        """
        Serialise the graph's edges to CSV, one row per ``LineageEdge``.

        Columns
        -------
        Source      - label of the edge's source node (falls back to
                      its id when the label is empty; the raw
                      ``source_node_id`` if the node itself is missing)
        Target      - label of the edge's target node (same fallback
                      rules as Source)
        Edge Type   - ``edge.edge_type.value`` (e.g. "DATA_FLOW")
        Rule        - ``edge.rule``
        Expression  - ``edge.expression``

        Field quoting/escaping is handled by the standard ``csv``
        module, so values containing commas, quotes, or newlines are
        safe.
        """
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["Source", "Target", "Edge Type", "Rule", "Expression"])

        for edge in self.edges:
            src_node = self.get_node(edge.source_node_id)
            tgt_node = self.get_node(edge.target_node_id)
            src_label = (src_node.label or src_node.id) if src_node else edge.source_node_id
            tgt_label = (tgt_node.label or tgt_node.id) if tgt_node else edge.target_node_id
            writer.writerow([
                src_label,
                tgt_label,
                edge.edge_type.value,
                edge.rule,
                edge.expression,
            ])

        csv_str = buf.getvalue()

        try:
            rows = list(csv.reader(io.StringIO(csv_str)))
        except csv.Error as e:
            raise ValueError(f"Generated CSV failed to parse: {e}") from e

        expected_rows = self.edge_count + 1  # header + one row per edge
        if len(rows) != expected_rows:
            raise ValueError(
                f"Generated CSV row count mismatch: expected {expected_rows}, got {len(rows)}"
            )
        if any(len(row) != 5 for row in rows):
            raise ValueError("Generated CSV has rows with an unexpected column count")

        return csv_str

    def neighbors(self, node_id: str, direction: str = "both") -> list["LineageNode"]:
        """Return neighboring nodes.

        Parameters
        ----------
        node_id   : ID of the node to query.
        direction : ``"out"`` for successors, ``"in"`` for predecessors,
                    ``"both"`` for all neighbours (outgoing first, then incoming).
        """
        result_ids: list[str] = []
        seen: set[str] = set()

        if direction in ("out", "both"):
            for edge in self.edges_from(node_id):
                nid = edge.target_node_id
                if nid not in seen:
                    result_ids.append(nid)
                    seen.add(nid)

        if direction in ("in", "both"):
            for edge in self.edges_to(node_id):
                nid = edge.source_node_id
                if nid not in seen:
                    result_ids.append(nid)
                    seen.add(nid)

        return [self._nodes[nid] for nid in result_ids if nid in self._nodes]

    @classmethod
    def from_json(cls, json_str: str) -> "LineageGraph":
        """Reconstruct a LineageGraph from a JSON string produced by :meth:`to_json`."""
        data = json.loads(json_str)

        nodes: list[LineageNode] = []
        for nd in data.get("nodes", []):
            meta = nd.get("metadata", {})
            nodes.append(
                LineageNode(
                    id=nd["id"],
                    node_type=NodeType(nd.get("node_type", NodeType.COMPONENT)),
                    label=nd.get("label", ""),
                    job_name=nd.get("job_name", ""),
                    physical_identity=nd.get("physical_identity", ""),
                    system_type=nd.get("system_type", ""),
                    database=nd.get("database", ""),
                    schema=nd.get("schema", ""),
                    table=nd.get("table", ""),
                    component_name=nd.get("component_name", ""),
                    component_type=nd.get("component_type", ""),
                    metadata=meta if isinstance(meta, dict) else {},
                )
            )

        graph = cls(nodes=nodes)

        for ed in data.get("edges", []):
            edge = LineageEdge(
                source_node_id=ed["source_node_id"],
                target_node_id=ed["target_node_id"],
                edge_type=EdgeType(ed.get("edge_type", EdgeType.DATA_FLOW)),
                job_name=ed.get("job_name", ""),
                rule=ed.get("rule", ""),
                rule_type=ed.get("rule_type", ""),
                expression=ed.get("expression", ""),
                source_column=ed.get("source_column", ""),
                target_column=ed.get("target_column", ""),
                metadata=ed.get("metadata", {}),
            )
            try:
                graph.add_edge(edge)
            except ValueError:
                pass  # skip edges whose nodes weren't restored

        return graph

    def to_mermaid(self) -> str:
        """Serialise the graph to a Mermaid flowchart string (graph LR)."""
        lines = ["graph LR"]
        for node in self.nodes:
            safe_id = node.id.replace(":", "_").replace(".", "_").replace(" ", "_")
            label = node.label or node.id
            lines.append(f'    {safe_id}["{label}"]')
        for edge in self.edges:
            src_id = edge.source_node_id.replace(":", "_").replace(".", "_").replace(" ", "_")
            tgt_id = edge.target_node_id.replace(":", "_").replace(".", "_").replace(" ", "_")
            rule = edge.rule or edge.edge_type
            lines.append(f'    {src_id} -->|"{rule}"| {tgt_id}')
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"LineageGraph(nodes={self.node_count}, edges={self.edge_count})"
        )


# ────────────────────────────────────────────────────────────────────────────
# LineagePath
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class LineagePath:
    """An ordered sequence of nodes connected by edges in a LineageGraph."""

    nodes: list[LineageNode] = field(default_factory=list)
    edges: list[LineageEdge] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate that nodes and edges form a contiguous chain."""
        if not self.nodes:
            return
        if len(self.edges) != len(self.nodes) - 1:
            raise ValueError(
                f"LineagePath requires exactly len(nodes)-1 edges; "
                f"got {len(self.nodes)} nodes and {len(self.edges)} edges."
            )
        for i, edge in enumerate(self.edges):
            if edge.source_node_id != self.nodes[i].id or edge.target_node_id != self.nodes[i + 1].id:
                raise ValueError(
                    f"Edge at position {i} does not connect nodes[{i}] → nodes[{i+1}]: "
                    f"expected {self.nodes[i].id} → {self.nodes[i+1].id}, "
                    f"got {edge.source_node_id} → {edge.target_node_id}."
                )

    @classmethod
    def single_node(cls, node: LineageNode) -> "LineagePath":
        return cls(nodes=[node], edges=[])

    @classmethod
    def from_edges(cls, graph: "LineageGraph", edges: list[LineageEdge]) -> "LineagePath":
        """Build a LineagePath from an ordered list of edges within *graph*."""
        if not edges:
            raise ValueError("from_edges requires at least one edge.")
        nodes: list[LineageNode] = []
        first_src = graph.get_node(edges[0].source_node_id)
        if first_src is None:
            raise ValueError(f"Node '{edges[0].source_node_id}' not found in graph.")
        nodes.append(first_src)
        for edge in edges:
            tgt = graph.get_node(edge.target_node_id)
            if tgt is None:
                raise ValueError(f"Node '{edge.target_node_id}' not found in graph.")
            nodes.append(tgt)
        return cls(nodes=nodes, edges=list(edges))

    @classmethod
    def from_dict(cls, data: dict, graph: "LineageGraph" = None) -> "LineagePath":
        """Reconstruct a LineagePath from the dict produced by :meth:`to_dict`."""
        node_entries = data.get("nodes", [])
        # Support both old format (list of str) and new format (list of {id, label})
        node_ids = []
        node_labels = {}
        for entry in node_entries:
            if isinstance(entry, dict):
                nid = entry.get("id", "")
                node_ids.append(nid)
                node_labels[nid] = entry.get("label", nid)
            else:
                node_ids.append(str(entry))
                node_labels[str(entry)] = str(entry)
        if graph is not None:
            nodes = [graph.get_node(nid) for nid in node_ids]
            nodes = [n for n in nodes if n is not None]
            # Attempt to recover edges from graph if available
            edges: list[LineageEdge] = []
            for i in range(len(nodes) - 1):
                src_id = nodes[i].id
                tgt_id = nodes[i + 1].id
                candidates = [e for e in graph.edges_from(src_id) if e.target_node_id == tgt_id]
                if candidates:
                    edges.append(candidates[0])
            return cls(nodes=nodes, edges=edges)
        # Without graph context, reconstruct from stored edge data if present
        edge_data = data.get("edges", [])
        stub_nodes = [LineageNode(id=nid, node_type=NodeType.COMPONENT, label=node_labels.get(nid, nid), job_name="") for nid in node_ids]
        stub_edges = []
        for ed in edge_data:
            stub_edges.append(LineageEdge(
                source_node_id=ed.get("source_node_id", ""),
                target_node_id=ed.get("target_node_id", ""),
                edge_type=EdgeType.DATA_FLOW,
                rule=ed.get("rule", ""),
                expression=ed.get("expression", ""),
            ))
        # Use object.__setattr__ to bypass dataclass validation for stub
        obj = object.__new__(cls)
        object.__setattr__(obj, "nodes", stub_nodes)
        object.__setattr__(obj, "edges", stub_edges)
        return obj

    def extend(self, edge: LineageEdge, node: LineageNode) -> "LineagePath":
        return LineagePath(nodes=list(self.nodes) + [node], edges=list(self.edges) + [edge])

    @property
    def hop_count(self) -> int:
        return len(self.edges)

    @property
    def expressions(self) -> list[str]:
        """Return expressions from all edges in the path (non-empty only)."""
        return [e.expression for e in self.edges if e.expression]

    @property
    def start_node(self) -> LineageNode:
        return self.nodes[0]

    @property
    def end_node(self) -> LineageNode:
        return self.nodes[-1]

    def describe(self) -> str:
        if not self.edges:
            return " → ".join(n.label or n.id for n in self.nodes)
        parts: list[str] = []
        for i, edge in enumerate(self.edges):
            src_label = self.nodes[i].label or self.nodes[i].id
            rule = edge.rule or edge.edge_type or ""
            parts.append(f"{src_label} --[{rule}]-->")
        parts.append(self.nodes[-1].label or self.nodes[-1].id)
        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            "nodes": [{"id": n.id, "label": n.label or n.id} for n in self.nodes],
            "edges": [
                {
                    "source_node_id": e.source_node_id,
                    "target_node_id": e.target_node_id,
                    "rule": e.rule,
                    "expression": e.expression,
                }
                for e in self.edges
            ],
            "hop_count": self.hop_count,
        }
