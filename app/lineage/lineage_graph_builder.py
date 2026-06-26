"""
lineage_graph_builder.py
========================
Translates ColumnMapping / MappingRuleDetail domain objects into a
LineageGraph with a canonical three-tier node layout:

    Source Column  (SOURCE_TABLE node)
         ↓
    Transformation (COMPONENT node  — the tMap)
         ↓
    Target Column  (TARGET_TABLE node)

Additionally:
    • Lookup tables   → LOOKUP_TABLE nodes, wired via LOOKUP edges
    • Join conditions → JOIN edges between the relevant source/lookup nodes
    • Expressions, filters, and join metadata are stored on the edges
      and/or in node metadata so downstream traversal / UI code can
      introspect them without re-parsing the raw XML.

Physical table resolution
-------------------------
When a ``component_physical_map`` is supplied (a
``dict[unique_name → PhysicalTableRef]`` produced by
``source_target_extractor.build_component_physical_map()``), every node
whose label would otherwise show a raw Talend component identifier
(e.g. ``tMysqlInput_1``) is replaced with the resolved qualified
name from the physical ref (e.g. ``MYSQL.CUSTOMERS``).

Resolution applies to:
  • SOURCE_TABLE nodes  — resolved from the source_component on the mapping
  • TARGET_TABLE nodes  — resolved from the target_component on the mapping
  • LOOKUP_TABLE nodes  — resolved from the lookup table's source component
  • COMPONENT nodes     — their label stays as the tMap name, but resolved
                          input/output physical names are stored in metadata

Fallback: if ``component_physical_map`` is absent or has no entry for a
given component name, all existing behaviour is preserved unchanged.

LineageNode metadata fields (Phase 3)
--------------------------------------
Every node produced by this builder now carries six first-class
attributes in addition to the pre-existing ``system_type`` and
``physical_identity`` fields.  All are accessible as plain attributes
on the returned ``LineageNode`` instance:

    system_type     (str)  Technology label — "MySQL", "Snowflake", "File", …
    database        (str)  Database / catalog name  (e.g. "customers_db")
    schema          (str)  Schema / owner name      (e.g. "dbo", "HR")
    table           (str)  Physical table name      (e.g. "CUSTOMERS")
    component_name  (str)  Talend unique component name (e.g. "tMysqlInput_1")
    component_type  (str)  Talend component type    (e.g. "tMysqlInput")

Node type population summary:

    SOURCE_TABLE  → all six fields from the source component's PhysicalTableRef
    TARGET_TABLE  → all six fields from the target component's PhysicalTableRef
    LOOKUP_TABLE  → all six fields from the matched PhysicalTableRef (if found)
    COMPONENT     → component_name / component_type only (no physical table)

The same six values are also mirrored into ``node.metadata`` under the
same key names for backwards compatibility with callers that read from
the metadata dict.

Design constraints (inherited from lineage_model.py):
    - No dependency on Streamlit.
    - No dependency on app.parser.*  — all input arrives as already-
      converted ColumnMapping / MappingRuleDetail instances (produced
      by app.ui.column_mapping_dto), plus an optional pre-built
      component_physical_map.
    - No UI rendering.

Public API
----------
    build_graph(
        mappings              : list[ColumnMapping],
        rule_details          : list[MappingRuleDetail],
        job_name              : str = "",
        system_type           : str = "",
        component_physical_map: dict[str, PhysicalTableRef] | None = None,
    ) -> LineageGraph

    build_graphs_for_jobs(
        jobs : list[dict],
        # each dict may include "component_physical_map"
    ) -> dict[str, LineageGraph]

    merge_job_graphs(
        graphs : dict[str, LineageGraph],
    ) -> LineageGraph
"""

from __future__ import annotations

import copy
import hashlib
import logging
import threading
from typing import Optional

from app.lineage.lineage_model import (
    EdgeType,
    LineageEdge,
    LineageGraph,
    LineageNode,
    NodeType,
)
from app.ui.column_mapping_model import ColumnMapping, MappingRuleDetail

# PhysicalTableRef is imported for type hints; caller may not always provide it
try:
    from app.parser.source_target_extractor import PhysicalTableRef
except ImportError:
    PhysicalTableRef = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# Graph build cache
# ────────────────────────────────────────────────────────────────────────────
# Keyed on a content hash of (mappings, rule_details, job_name, system_type,
# component_physical_map) so identical inputs skip a full rebuild. Cached
# graphs are deep-copied out so callers can mutate them freely.
_GRAPH_CACHE: dict[str, LineageGraph] = {}
_GRAPH_CACHE_LOCK = threading.Lock()


def _hash_update(hasher, obj) -> None:
    """
    Feed a canonical, type/length-tagged encoding of ``obj`` into ``hasher``.

    Single pass over the structure (O(n) total): no intermediate strings are
    built or concatenated, so this scales linearly with the size of
    ``mappings`` / ``rule_details`` instead of the O(n^2) cost of repeatedly
    joining/concatenating string representations. Each value is prefixed
    with a type tag and explicit length so structurally different inputs
    (e.g. different nesting or string boundaries) can never collide on the
    same byte stream.
    """
    if obj is None:
        hasher.update(b"N")
    elif isinstance(obj, bool):
        hasher.update(b"B1" if obj else b"B0")
    elif isinstance(obj, dict):
        hasher.update(f"D{len(obj)}:".encode("utf-8"))
        for k in sorted(obj.keys(), key=repr):
            _hash_update(hasher, k)
            _hash_update(hasher, obj[k])
    elif isinstance(obj, (list, tuple)):
        hasher.update(f"{'L' if isinstance(obj, list) else 'T'}{len(obj)}:".encode("utf-8"))
        for v in obj:
            _hash_update(hasher, v)
    elif hasattr(obj, "__dict__"):
        hasher.update(f"O:{type(obj).__name__}:".encode("utf-8"))
        _hash_update(hasher, vars(obj))
    else:
        data = repr(obj).encode("utf-8")
        hasher.update(f"P{len(data)}:".encode("utf-8"))
        hasher.update(data)


def _build_graph_cache_key(
    mappings,
    rule_details,
    job_name: str,
    system_type: str,
    component_physical_map,
) -> str:
    hasher = hashlib.sha256()
    _hash_update(hasher, mappings)
    _hash_update(hasher, rule_details)
    _hash_update(hasher, job_name)
    _hash_update(hasher, system_type)
    _hash_update(hasher, component_physical_map)
    return hasher.hexdigest()


def clear_graph_cache() -> None:
    """Drop all cached graphs. Call when underlying source data changes."""
    with _GRAPH_CACHE_LOCK:
        _GRAPH_CACHE.clear()


# ────────────────────────────────────────────────────────────────────────────
# Node-ID helpers
# ────────────────────────────────────────────────────────────────────────────

def _source_node_id(job_name: str, table: str, column: str) -> str:
    """Deterministic id for a source column node."""
    return f"{job_name}:source_table:{table}.{column}"


def _target_node_id(job_name: str, table: str, column: str) -> str:
    """Deterministic id for a target column node."""
    return f"{job_name}:target_table:{table}.{column}"


def _component_node_id(job_name: str, component: str) -> str:
    """Deterministic id for a tMap/component node."""
    return f"{job_name}:component:{component}"


def _lookup_node_id(job_name: str, table: str) -> str:
    """Deterministic id for a lookup-table node."""
    return f"{job_name}:lookup_table:{table}"


def _physical_id(system_type: str, table: str) -> str:
    """
    A normalised cross-job identity key, e.g. ``"mysql:customers"``.
    Used by ``LineageGraph.find_nodes_by_physical_identity()`` when
    stitching jobs into a repository-wide graph.

    Always namespaced by system_type, even when unknown, so that two
    different jobs that both have an unqualified table named e.g.
    "customers" on different (or unresolved) systems are never treated
    as the same physical entity. An empty table yields no identity key
    at all (callers should treat "" as "no physical identity").
    """
    if not table:
        return ""
    return f"{(system_type or 'unknown').lower()}:{table.lower()}"


# ────────────────────────────────────────────────────────────────────────────
# Physical resolution helpers
# ────────────────────────────────────────────────────────────────────────────

def _resolve_label_for_table(
    component_name: str,
    tmap_table_name: str,
    component_physical_map: Optional[dict],
) -> tuple[str, str, str]:
    """
    Attempt to resolve a display label and physical_identity key for a
    source/target table node whose Talend internal name is
    ``tmap_table_name`` (e.g. "row1") and whose connected component
    is ``component_name`` (e.g. "tMysqlInput_1").

    Returns ``(label, physical_identity, db_type)`` where:
      - ``label``             is ``"MYSQL.CUSTOMERS"`` when resolved, or
                              ``tmap_table_name`` when not.
      - ``physical_identity`` is a normalised lowercase key for cross-job
                              matching (e.g. ``"mysql:customers"``), or
                              the raw table name when unresolved.
      - ``db_type``           is the technology label (e.g. ``"MySQL"``), or
                              ``""`` when unresolved.

    Resolution logic:
      1. Look up ``component_name`` in ``component_physical_map``.
      2. If found and the ref is resolved, use ``ref.qualified_name``
         as the label and ``ref.physical_key`` as the identity.
      3. Otherwise fall through to the tmap-internal table name.
    """
    if not component_physical_map or not component_name:
        return tmap_table_name, tmap_table_name, ""

    ref = component_physical_map.get(component_name)
    if ref is None:
        return tmap_table_name, tmap_table_name, ""

    if ref.is_resolved:
        label = ref.qualified_name
        key   = ref.physical_key or tmap_table_name
        return label, key, ref.db_type

    # Ref exists but nothing resolved (e.g. all context vars) — keep internal name
    return tmap_table_name, tmap_table_name, ref.db_type


# ────────────────────────────────────────────────────────────────────────────
# Rule-type → EdgeType mapping
# ────────────────────────────────────────────────────────────────────────────

def _edge_type_for_rule(rule_type: str, rule: str) -> EdgeType:
    """
    Derive an EdgeType from a ColumnMapping's rule_type / rule label.

    - ``"join"``  rule_type → JOIN edge
    - lookup-related rules  → stays DATA_FLOW (lookup edges come from
      MappingRuleDetail, not ColumnMapping rows)
    - everything else       → DATA_FLOW
    """
    if rule_type == "join" or "join" in rule.lower():
        return EdgeType.JOIN
    return EdgeType.DATA_FLOW


# ────────────────────────────────────────────────────────────────────────────
# Internal helpers — nodes
# ────────────────────────────────────────────────────────────────────────────

def _ensure_source_node(
    graph: LineageGraph,
    job_name: str,
    mapping: ColumnMapping,
    system_type: str,
    component_physical_map: Optional[dict],
) -> LineageNode:
    """Add (or merge) a SOURCE_TABLE node and return it."""
    node_id = _source_node_id(job_name, mapping.source_table, mapping.source_column)

    # Attempt physical resolution of the connected source component
    resolved_label, phys_id, resolved_db_type = _resolve_label_for_table(
        component_name=mapping.source_component,
        tmap_table_name=mapping.source_table,
        component_physical_map=component_physical_map,
    )

    # Full column-qualified display label
    label = (
        f"{resolved_label}.{mapping.source_column}"
        if mapping.source_column
        else resolved_label
    )

    # Use resolved db_type when system_type was not provided by the caller
    effective_system = system_type or resolved_db_type

    # Unpack PhysicalTableRef fields for the six first-class node attributes
    ref = (
        component_physical_map.get(mapping.source_component)
        if component_physical_map and mapping.source_component
        else None
    )

    node = LineageNode(
        id=node_id,
        node_type=NodeType.SOURCE_TABLE,
        label=label,
        system_type=effective_system,
        job_name=job_name,
        physical_identity=phys_id,
        # ── Six first-class physical-table metadata fields (Phase 3) ─────────
        database=       ref.database       if ref else "",
        schema=         ref.schema         if ref else "",
        table=          ref.table          if ref else mapping.source_table,
        component_name= ref.unique_name    if ref else mapping.source_component,
        component_type= ref.component_type if ref else "",
        # system_type already set above via effective_system
        metadata={
            "table":              mapping.source_table,
            "column":             mapping.source_column,
            "component":          mapping.source_component,
            "resolved_table":     resolved_label,
            "db_type":            resolved_db_type,
        },
    )
    return graph.add_node(node)


def _ensure_target_node(
    graph: LineageGraph,
    job_name: str,
    mapping: ColumnMapping,
    system_type: str,
    component_physical_map: Optional[dict],
) -> LineageNode:
    """Add (or merge) a TARGET_TABLE node and return it."""
    node_id = _target_node_id(job_name, mapping.target_table, mapping.target_column)

    # Attempt physical resolution of the connected target component
    resolved_label, phys_id, resolved_db_type = _resolve_label_for_table(
        component_name=mapping.target_component,
        tmap_table_name=mapping.target_table,
        component_physical_map=component_physical_map,
    )

    label = (
        f"{resolved_label}.{mapping.target_column}"
        if mapping.target_column
        else resolved_label
    )

    effective_system = system_type or resolved_db_type

    # Unpack PhysicalTableRef fields for the six first-class node attributes
    ref = (
        component_physical_map.get(mapping.target_component)
        if component_physical_map and mapping.target_component
        else None
    )

    node = LineageNode(
        id=node_id,
        node_type=NodeType.TARGET_TABLE,
        label=label,
        system_type=effective_system,
        job_name=job_name,
        physical_identity=phys_id,
        # ── Six first-class physical-table metadata fields (Phase 3) ─────────
        database=       ref.database       if ref else "",
        schema=         ref.schema         if ref else "",
        table=          ref.table          if ref else mapping.target_table,
        component_name= ref.unique_name    if ref else mapping.target_component,
        component_type= ref.component_type if ref else "",
        metadata={
            "table":          mapping.target_table,
            "column":         mapping.target_column,
            "component":      mapping.target_component,
            "resolved_table": resolved_label,
            "db_type":        resolved_db_type,
        },
    )
    return graph.add_node(node)


def _ensure_component_node(
    graph: LineageGraph,
    job_name: str,
    component_name: str,
    rule_details_by_table: dict[str, list[MappingRuleDetail]],
    component_physical_map: Optional[dict],
) -> LineageNode:
    """
    Add (or merge) a COMPONENT node representing a tMap instance.

    The node's metadata records:
      - All expressions, filters, joins and lookups known from the
        associated MappingRuleDetail entries for this component.
      - Resolved input/output physical names when a
        component_physical_map is provided (stored in metadata for
        downstream inspection; the node label stays as the tMap name
        since it represents the transform, not a table).
    """
    node_id = _component_node_id(job_name, component_name)

    # Collect metadata from rule details
    expressions: list[str] = []
    filters: list[str] = []
    joins: list[dict] = []
    lookups: list[dict] = []

    for table, rules in rule_details_by_table.items():
        for rd in rules:
            if rd.filter_expression:
                filters.append(rd.filter_expression)
            if rd.join_type:
                joins.append({
                    "table":      rd.table or table,
                    "join_type":  rd.join_type,
                    "match_mode": rd.match_mode,
                })
            if rd.rule_type == "Lookup":
                lookups.append({
                    "table":      rd.table or table,
                    "match_mode": rd.match_mode,
                    "filter":     rd.filter_expression,
                })

    # Attach resolved input/output physical info from the physical map
    resolved_inputs: list[str] = []
    resolved_outputs: list[str] = []
    if component_physical_map:
        for uid, ref in component_physical_map.items():
            # We can't know which components are inputs vs outputs without
            # re-checking component_type; store all for downstream use
            if ref.is_resolved:
                ct = ref.component_type.lower()
                if "input" in ct or "row" in ct:
                    resolved_inputs.append(ref.qualified_name)
                elif "output" in ct:
                    resolved_outputs.append(ref.qualified_name)

    node = LineageNode(
        id=node_id,
        node_type=NodeType.COMPONENT,
        label=component_name,
        job_name=job_name,
        # ── Six first-class physical-table metadata fields (Phase 3) ─────────
        # COMPONENT nodes represent a tMap transform, not a physical table;
        # database/schema/table are left empty.  component_name/type are set.
        component_name=component_name,
        component_type="tMap",          # tMap is the only COMPONENT node type
        metadata={
            "component":        component_name,
            "expressions":      expressions,
            "filters":          filters,
            "joins":            joins,
            "lookups":          lookups,
            "resolved_inputs":  resolved_inputs,
            "resolved_outputs": resolved_outputs,
        },
    )
    return graph.add_node(node)


def _ensure_lookup_node(
    graph: LineageGraph,
    job_name: str,
    table: str,
    rule: MappingRuleDetail,
    system_type: str,
    component_physical_map: Optional[dict],
) -> LineageNode:
    """
    Add (or merge) a LOOKUP_TABLE node and return it.

    Physical resolution: the ``table`` name here is the tMap-internal
    input-table name (e.g. ``"lookup1"``).  We attempt to resolve it
    against the physical map by scanning for a component whose
    unique_name or resolved table name matches.
    """
    node_id = _lookup_node_id(job_name, table)

    # Try to find a physical ref whose resolved table matches this lookup name
    resolved_label = table
    phys_id = table
    resolved_db_type = ""
    # Capture the matched ref for the six first-class node attributes
    matched_ref = None
    if component_physical_map:
        for uid, ref in component_physical_map.items():
            if ref.is_resolved and (
                ref.table.lower() == table.lower()
                or uid.lower() == table.lower()
            ):
                resolved_label = ref.qualified_name
                phys_id = ref.physical_key or table
                resolved_db_type = ref.db_type
                matched_ref = ref
                break

    effective_system = system_type or resolved_db_type

    node = LineageNode(
        id=node_id,
        node_type=NodeType.LOOKUP_TABLE,
        label=resolved_label,
        system_type=effective_system,
        job_name=job_name,
        physical_identity=phys_id,
        # ── Six first-class physical-table metadata fields (Phase 3) ─────────
        database=       matched_ref.database       if matched_ref else "",
        schema=         matched_ref.schema         if matched_ref else "",
        table=          matched_ref.table          if matched_ref else table,
        component_name= matched_ref.unique_name    if matched_ref else "",
        component_type= matched_ref.component_type if matched_ref else "",
        metadata={
            "table":          table,
            "match_mode":     rule.match_mode,
            "filter":         rule.filter_expression,
            "join_type":      rule.join_type,
            "resolved_table": resolved_label,
            "db_type":        resolved_db_type,
        },
    )
    return graph.add_node(node)


# ────────────────────────────────────────────────────────────────────────────
# Internal helpers — edges
# ────────────────────────────────────────────────────────────────────────────

def _add_column_edges(
    graph: LineageGraph,
    job_name: str,
    mapping: ColumnMapping,
    src_node: LineageNode,
    comp_node: LineageNode,
    tgt_node: LineageNode,
) -> None:
    """
    Wire Source → Transformation → Target for one ColumnMapping.

    Source → Component carries the raw expression (if any).
    Component → Target carries the rule label and rule_type.
    """
    edge_type = _edge_type_for_rule(mapping.rule_type, mapping.rule)

    # Source Column  →  Transformation (tMap)
    src_to_comp = LineageEdge(
        source_node_id=src_node.id,
        target_node_id=comp_node.id,
        edge_type=edge_type,
        job_name=job_name,
        rule=mapping.rule,
        rule_type=mapping.rule_type,
        expression=mapping.expression,
        source_column=mapping.source_column,
        target_column=mapping.source_column,  # same column entering tMap
        metadata={"phase": "input"},
    )
    try:
        graph.add_edge(src_to_comp)
    except ValueError as exc:
        logger.debug("Skipping duplicate/invalid src→comp edge: %s", exc)

    # Transformation (tMap)  →  Target Column
    comp_to_tgt = LineageEdge(
        source_node_id=comp_node.id,
        target_node_id=tgt_node.id,
        edge_type=edge_type,
        job_name=job_name,
        rule=mapping.rule,
        rule_type=mapping.rule_type,
        expression=mapping.expression,
        source_column=mapping.source_column,
        target_column=mapping.target_column,
        metadata={"phase": "output"},
    )
    try:
        graph.add_edge(comp_to_tgt)
    except ValueError as exc:
        logger.debug("Skipping duplicate/invalid comp→tgt edge: %s", exc)


def _add_lookup_edge(
    graph: LineageGraph,
    job_name: str,
    comp_node: LineageNode,
    lookup_node: LineageNode,
    rule: MappingRuleDetail,
) -> None:
    """Wire a LOOKUP edge from the tMap component into the lookup table."""
    edge = LineageEdge(
        source_node_id=comp_node.id,
        target_node_id=lookup_node.id,
        edge_type=EdgeType.LOOKUP,
        job_name=job_name,
        rule="Lookup",
        rule_type="lookup",
        expression=rule.filter_expression,
        metadata={
            "match_mode": rule.match_mode,
            "join_type":  rule.join_type,
        },
    )
    try:
        graph.add_edge(edge)
    except ValueError as exc:
        logger.debug("Skipping invalid lookup edge: %s", exc)


def _add_join_edge(
    graph: LineageGraph,
    job_name: str,
    comp_node: LineageNode,
    lookup_node: LineageNode,
    rule: MappingRuleDetail,
) -> None:
    """Wire a JOIN edge from the tMap component into the join/lookup table."""
    edge = LineageEdge(
        source_node_id=comp_node.id,
        target_node_id=lookup_node.id,
        edge_type=EdgeType.JOIN,
        job_name=job_name,
        rule=f"Join ({rule.join_type})" if rule.join_type else "Join",
        rule_type="join",
        expression=rule.filter_expression,
        metadata={
            "join_type":  rule.join_type,
            "match_mode": rule.match_mode,
            "filter":     rule.filter_expression,
        },
    )
    try:
        graph.add_edge(edge)
    except ValueError as exc:
        logger.debug("Skipping invalid join edge: %s", exc)


# ────────────────────────────────────────────────────────────────────────────
# Rule-detail grouping helper
# ────────────────────────────────────────────────────────────────────────────

def _group_rule_details(
    rule_details: list[MappingRuleDetail],
) -> dict[str, list[MappingRuleDetail]]:
    """
    Group MappingRuleDetail objects by their ``table`` field.
    Returns ``{table_name: [MappingRuleDetail, …]}``.
    """
    grouped: dict[str, list[MappingRuleDetail]] = {}
    for rd in rule_details:
        key = rd.table or ""
        grouped.setdefault(key, []).append(rd)
    return grouped


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

def build_graph(
    mappings: list[ColumnMapping],
    rule_details: list[MappingRuleDetail],
    job_name: str = "",
    system_type: str = "",
    component_physical_map: Optional[dict] = None,
) -> LineageGraph:
    """
    Build a LineageGraph for a single Talend job.

    Parameters
    ----------
    mappings : list[ColumnMapping]
        Column-level mappings extracted from a job's tMap components
        (as produced by ``column_mapping_dto.from_parser_row()``).
    rule_details : list[MappingRuleDetail]
        Table-level rule entries (joins, lookups, filters) extracted
        from the same job (as produced by ``column_mapping_dto.from_rule_row()``).
    job_name : str
        Name of the Talend job; used to prefix all node IDs for
        uniqueness and to set ``job_name`` on every node and edge.
    system_type : str
        Technology label for source/target nodes, e.g. ``"MySQL"``,
        ``"Snowflake"``, ``"File"``.  Used to build ``physical_identity``
        keys for cross-job node matching.  When ``component_physical_map``
        is provided, per-component db_type values take precedence.
    component_physical_map : dict[str, PhysicalTableRef] | None
        Optional mapping of ``unique_name → PhysicalTableRef`` produced
        by ``source_target_extractor.build_component_physical_map()``.
        When provided, every node whose label would show a raw component
        identifier (e.g. ``tMysqlInput_1``) is instead labelled with the
        resolved physical name (e.g. ``MYSQL.CUSTOMERS``).  Fallback to
        the tMap-internal table/column name when no matching ref exists.

    Returns
    -------
    LineageGraph
        A graph whose nodes follow the canonical three-tier layout::

            Source Column  (SOURCE_TABLE node)
                  ↓  [DATA_FLOW / JOIN edge — carries expression]
            Transformation (COMPONENT node — the tMap)
                  ↓  [DATA_FLOW / JOIN edge — carries rule label]
            Target Column  (TARGET_TABLE node)

        Plus LOOKUP_TABLE nodes wired via LOOKUP/JOIN edges for any
        tables identified as lookups or joins in ``rule_details``.

    Physical resolution on nodes
    ----------------------------
    When ``component_physical_map`` is supplied:
      - SOURCE_TABLE / TARGET_TABLE ``label``            → resolved qualified name
        (e.g. ``"MYSQL.CUSTOMERS.customer_id"``)
      - SOURCE_TABLE / TARGET_TABLE ``physical_identity`` → ``ref.physical_key``
      - SOURCE_TABLE / TARGET_TABLE ``system_type``      → ``ref.db_type``
      - SOURCE_TABLE / TARGET_TABLE ``metadata``         → includes
        ``"resolved_table"`` (e.g. ``"MYSQL.CUSTOMERS"``) and ``"db_type"``
      - COMPONENT ``metadata``                           → includes
        ``"resolved_inputs"`` and ``"resolved_outputs"`` lists
      - LOOKUP_TABLE                                      → resolved when the
        lookup's tMap-internal table name matches a ref's physical table name

    Stored per edge / node
    ----------------------
    Expressions   — ``LineageEdge.expression`` (raw tMap expression)
    Filters       — ``LineageNode.metadata["filters"]`` on the COMPONENT node;
                    also ``LineageEdge.expression`` for filter-type rule rows
    Joins         — ``LineageEdge.edge_type == EdgeType.JOIN``; join metadata
                    stored in ``LineageEdge.metadata``
    Lookups       — ``LineageEdge.edge_type == EdgeType.LOOKUP``; lookup
                    metadata stored in ``LineageEdge.metadata``
    """
    cache_key = _build_graph_cache_key(
        mappings, rule_details, job_name, system_type, component_physical_map
    )
    with _GRAPH_CACHE_LOCK:
        cached = _GRAPH_CACHE.get(cache_key)
    if cached is not None:
        logger.debug("build_graph: cache hit for job %r", job_name)
        return copy.deepcopy(cached)

    graph = LineageGraph()

    if not mappings and not rule_details:
        logger.debug("build_graph: no mappings or rule_details for job %r", job_name)
        with _GRAPH_CACHE_LOCK:
            _GRAPH_CACHE[cache_key] = graph
        return graph

    rule_details_by_table = _group_rule_details(rule_details)

    # ── Identify all component names from mappings ────────────────────────
    component_names: set[str] = set()
    for m in mappings:
        if m.source_component:
            component_names.add(m.source_component)
        if m.target_component:
            component_names.add(m.target_component)
    # Fall back: at least one synthetic component when mappings list is
    # non-empty but components are all blank (edge case from partial XML)
    if mappings and not component_names:
        component_names.add("tMap_1")

    # ── Pre-create component nodes (so edges can reference them) ─────────
    comp_nodes: dict[str, LineageNode] = {}
    for comp_name in component_names:
        comp_nodes[comp_name] = _ensure_component_node(
            graph, job_name, comp_name, rule_details_by_table, component_physical_map
        )

    # ── Process lookup / join tables from rule_details ────────────────────
    for table, rules in rule_details_by_table.items():
        for rd in rules:
            if rd.rule_type == "Lookup":
                lk_node = _ensure_lookup_node(
                    graph, job_name, table, rd, system_type, component_physical_map
                )
                for comp_node in comp_nodes.values():
                    _add_lookup_edge(graph, job_name, comp_node, lk_node, rd)

            elif rd.rule_type in ("Join", "") and rd.join_type:
                join_node = _ensure_lookup_node(
                    graph, job_name, table, rd, system_type, component_physical_map
                )
                for comp_node in comp_nodes.values():
                    _add_join_edge(graph, job_name, comp_node, join_node, rd)

    # ── Process column-level mappings ─────────────────────────────────────
    for mapping in mappings:
        if not mapping.source_column and not mapping.target_column:
            logger.debug(
                "Skipping mapping with no columns in job %r: %r → %r",
                job_name,
                mapping.source_component,
                mapping.target_component,
            )
            continue

        comp_name = mapping.source_component or mapping.target_component
        if comp_name not in comp_nodes:
            comp_nodes[comp_name] = _ensure_component_node(
                graph, job_name, comp_name, rule_details_by_table, component_physical_map
            )
        comp_node = comp_nodes[comp_name]

        src_node = _ensure_source_node(
            graph, job_name, mapping, system_type, component_physical_map
        )
        tgt_node = _ensure_target_node(
            graph, job_name, mapping, system_type, component_physical_map
        )

        _add_column_edges(graph, job_name, mapping, src_node, comp_node, tgt_node)

    logger.info(
        "build_graph: job=%r → %d nodes, %d edges (physical_map=%s)",
        job_name,
        graph.node_count,
        graph.edge_count,
        "yes" if component_physical_map else "no",
    )
    with _GRAPH_CACHE_LOCK:
        _GRAPH_CACHE[cache_key] = graph
    return graph


def build_graphs_for_jobs(
    jobs: list[dict],
) -> dict[str, LineageGraph]:
    """
    Build one LineageGraph per job from a list of job descriptors.

    Parameters
    ----------
    jobs : list[dict]
        Each entry is expected to have:
            ``"job_name"``              (str)
            ``"mappings"``              (list[ColumnMapping])
            ``"rule_details"``          (list[MappingRuleDetail])
            ``"system_type"``           (str, optional)
            ``"component_physical_map"``(dict[str, PhysicalTableRef], optional)
                                        — pre-built by
                                        ``source_target_extractor.build_component_physical_map()``

    Returns
    -------
    dict[str, LineageGraph]
        Mapping of ``job_name → LineageGraph``.
    """
    result: dict[str, LineageGraph] = {}
    for job in jobs:
        job_name    = job.get("job_name", "")
        mappings    = job.get("mappings", [])
        rule_details = job.get("rule_details", [])
        system_type = job.get("system_type", "")
        comp_map    = job.get("component_physical_map", None)
        graph = build_graph(
            mappings=mappings,
            rule_details=rule_details,
            job_name=job_name,
            system_type=system_type,
            component_physical_map=comp_map,
        )
        result[job_name] = graph
    return result


def merge_job_graphs(
    graphs: dict[str, LineageGraph],
) -> LineageGraph:
    """
    Merge per-job graphs into a single repository-wide LineageGraph.

    Nodes are combined and de-duplicated by id via
    ``LineageGraph.merge()`` / ``LineageNode.merged_with()``.
    Physical-identity bridging (linking the same real-world table
    across different jobs) is *not* performed here — that is the
    responsibility of a higher-level traversal module that can use
    ``LineageGraph.find_nodes_by_physical_identity()`` to locate
    candidates and then add explicit bridge edges between them.

    Parameters
    ----------
    graphs : dict[str, LineageGraph]
        Mapping of ``job_name → LineageGraph`` as returned by
        ``build_graphs_for_jobs()``.

    Returns
    -------
    LineageGraph
        The merged graph.
    """
    combined = LineageGraph()
    for job_name, graph in graphs.items():
        combined = combined.merge(graph)
        logger.debug("merge_job_graphs: merged %r → combined=%r", job_name, combined)
    logger.info(
        "merge_job_graphs: %d jobs → %d nodes, %d edges",
        len(graphs),
        combined.node_count,
        combined.edge_count,
    )
    return combined
