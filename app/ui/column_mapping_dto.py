"""
column_mapping_dto.py
Data-Transfer-Object helpers: convert raw parser dicts → typed model instances.

No parser files are imported or modified here.
All input data comes from:
  - TalendJobParser.extract_column_mappings() → list[dict]
  - TalendJobParser.extract_mapping_rules()   → list[dict]
"""

from __future__ import annotations
from collections import OrderedDict

from app.ui.column_mapping_model import ColumnMapping, MappingRuleDetail

# ── Rule → rule_type normalisation ───────────────────────────────────────────
_RULE_TYPE_MAP: dict[str, str] = {
    "Direct Copy":            "direct",
    "Direct Copy (Nullable)": "direct",
    "Type Cast":              "direct",
    "Context Variable":       "direct",
    "Join Key":               "join",
    "Conditional Expression": "expression",
    "String Concatenation":   "expression",
    "Function Transform":     "expression",
    "Arithmetic Expression":  "expression",
    "Cross-Table Reference":  "expression",
    "Expression Mapping":     "expression",
}


def from_parser_row(row: dict) -> ColumnMapping:
    """
    Convert one dict from TalendJobParser.extract_column_mappings()
    into a ColumnMapping instance.

    Expected dict keys (as produced by the parser):
        "Source Component", "Source Column", "Target Component",
        "Target Column", "Migration Rule", "Expression"

    The parser does not always expose Source Table / Target Table as
    separate fields — they are inferred from the component name by convention
    (e.g. "tMap_1.row1" stored as Source Component + Source Column).
    We split on "." where present to recover the table portion.
    """
    raw_src_comp = str(row.get("Source Component", "") or "")
    raw_tgt_comp = str(row.get("Target Component", "") or "")
    raw_src_col  = str(row.get("Source Column",    "") or "")
    raw_tgt_col  = str(row.get("Target Column",    "") or "")
    rule         = str(row.get("Migration Rule",   "") or "")
    expression   = str(row.get("Expression",       "") or "")

    # Split "table.column" into parts
    src_table, src_column = _split_table_col(raw_src_col, fallback_table=raw_src_comp)
    tgt_table, tgt_column = _split_table_col(raw_tgt_col, fallback_table=raw_tgt_comp)

    rule_type = _RULE_TYPE_MAP.get(rule, "expression" if expression else "direct")

    return ColumnMapping(
        source_component=raw_src_comp,
        source_table=src_table,
        source_column=src_column,
        target_component=raw_tgt_comp,
        target_table=tgt_table,
        target_column=tgt_column,
        rule=rule,
        expression=expression,
        rule_type=rule_type,
    )


def from_rule_row(row: dict) -> MappingRuleDetail:
    """
    Convert one dict from TalendJobParser.extract_mapping_rules()
    into a MappingRuleDetail instance.

    Expected dict keys:
        "Table", "Join Type", "Match Mode", "Filter Expression", "Rule Type"
    """
    return MappingRuleDetail(
        table=str(row.get("Table",            "") or ""),
        join_type=str(row.get("Join Type",    "") or ""),
        match_mode=str(row.get("Match Mode",  "") or ""),
        filter_expression=str(row.get("Filter Expression", "") or ""),
        rule_type=str(row.get("Rule Type",    "Output") or "Output"),
    )


def group_by_component_pair(
    mappings: list[ColumnMapping],
) -> dict[tuple[str, str], list[ColumnMapping]]:
    """
    Group a list of ColumnMapping objects by (source_component, target_component).

    Returns an OrderedDict preserving insertion order (most common pair first).
    """
    groups: dict[tuple[str, str], list[ColumnMapping]] = OrderedDict()
    for m in mappings:
        key = (m.source_component, m.target_component)
        groups.setdefault(key, []).append(m)
    return groups


# ── Internal helpers ──────────────────────────────────────────────────────────

def _split_table_col(value: str, fallback_table: str = "") -> tuple[str, str]:
    """
    Split a "table.column" string into (table, column).
    If no dot is present, use fallback_table and the whole value as the column.
    """
    if "." in value:
        parts = value.split(".", 1)
        return parts[0].strip(), parts[1].strip()
    return fallback_table, value
