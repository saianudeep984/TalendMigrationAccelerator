"""
column_mapping_model.py
Data models for the Column Mapping tab.

ColumnMapping     — one column-level mapping row extracted from a tMap.
MappingRuleDetail — one tMap rule entry (Output / Lookup / Reject / Expression Filter).
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ColumnMapping:
    """
    Represents a single column-level mapping inside a tMap component.

    Fields
    ------
    source_component : str
        Unique name of the tMap component, e.g. "tMap_1".
    source_table : str
        Input table name inside the tMap, e.g. "row1".
    source_column : str
        Column name in the source table.
    target_component : str
        Unique name of the tMap component (same as source_component for tMap).
    target_table : str
        Output table name inside the tMap, e.g. "out1".
    target_column : str
        Column name in the target table.
    rule : str
        Migration rule label, e.g. "Direct Copy", "Expression Mapping", "Join Key".
    expression : str
        Raw tMap expression string; empty string for direct copies.
    rule_type : str
        Normalised category: "direct" | "expression" | "join" | "aggregate".
    """

    source_component: str = ""
    source_table:     str = ""
    source_column:    str = ""
    target_component: str = ""
    target_table:     str = ""
    target_column:    str = ""
    rule:             str = ""
    expression:       str = ""
    rule_type:        str = "direct"


@dataclass
class MappingRuleDetail:
    """
    Represents a tMap-level rule entry (input table join/lookup/filter/output metadata).

    Fields
    ------
    table : str
        Table name this rule applies to.
    join_type : str
        E.g. "INNER_JOIN", "LEFT_OUTER_JOIN", or empty for output tables.
    match_mode : str
        E.g. "ALL_ROWS", "FIRST_ROW", or empty.
    filter_expression : str
        Optional filter/expression condition string.
    rule_type : str
        One of: "Output" | "Lookup" | "Reject" | "Expression Filter".
    """

    table:             str = ""
    join_type:         str = ""
    match_mode:        str = ""
    filter_expression: str = ""
    rule_type:         str = "Output"
