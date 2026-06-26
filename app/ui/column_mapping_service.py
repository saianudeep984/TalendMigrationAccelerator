"""
column_mapping_service.py
Service layer for loading column mapping data.

Wraps the parser calls so that column_mapping_page.py never imports
from app.parser.talend_xml_parser directly.

NOTE: "_colmap_" result caching is TEMPORARILY DISABLED. load_mappings()
always re-invokes the parser and never reads or writes the
st.session_state["_colmap_{job_name}"] cache entry. clear_mapping_cache()
is left intact as a no-op-safe utility for when caching is re-enabled.
"""

from __future__ import annotations
import os
import logging

import streamlit as st

from app.ui.column_mapping_model import ColumnMapping, MappingRuleDetail
from app.ui.column_mapping_dto import from_parser_row, from_rule_row

logger = logging.getLogger(__name__)


def load_mappings(
    job: dict,
) -> tuple[list[ColumnMapping], list[MappingRuleDetail]]:
    """
    Load column-level mappings and rule details for a job.

    Parameters
    ----------
    job : dict
        Job object from st.session_state["last_analysis_jobs"].
        Must contain "job_data" (with "job_name") and optionally "file_path".

    Returns
    -------
    (mappings, rule_details)
        mappings     : list[ColumnMapping]     — one entry per tMap column mapping
        rule_details : list[MappingRuleDetail] — one entry per tMap rule (join/lookup/filter)

    Both lists are empty when:
    - file_path is absent or not a valid .item file
    - The parser raises an exception
    - The job has no tMap components
    """
    st.warning("Column Mapping Cache Disabled")

    job_name = job.get("job_data", {}).get("job_name", "unknown")
    cache_key = f"_colmap_{job_name}"
    original_path = job.get("file_path", "")
    item_path = os.path.abspath(original_path) if original_path else ""
    file_exists = bool(item_path and os.path.isfile(item_path))
    file_size = os.path.getsize(item_path) if file_exists else 0
    file_ext = os.path.splitext(item_path)[1] if item_path else ""

    st.info(f'Original job["file_path"]: {original_path or "Not available"}')
    st.info(f"Resolved .item path: {item_path or 'Not available'}")
    st.info(f"File exists: {file_exists}")
    st.info(f"File size: {file_size} bytes")
    st.info(f"File extension: {file_ext or 'None'}")
    if not file_exists:
        st.error(f".item file does not exist: {item_path or original_path or 'Not available'}")

    # --- Caching temporarily disabled: always reload from parser ---
    # if cache_key in st.session_state:
    #     cached = st.session_state[cache_key]
    #     return cached["mappings"], cached["rule_details"]

    mappings:     list[ColumnMapping]     = []
    rule_details: list[MappingRuleDetail] = []

    if item_path and os.path.isfile(item_path):
        try:
            from app.parser.talend_xml_parser import TalendJobParser as _TJP
            import traceback

            parser = _TJP(item_path)

            raw_mappings = parser.extract_column_mappings() or []
            raw_rules    = parser.extract_mapping_rules()   or []

            # ── Raw parser counts ─────────────────────────────────────────────
            st.write(f"**Raw extract_column_mappings() rows:** {len(raw_mappings)}")
            st.write(f"**Raw extract_mapping_rules() rows:** {len(raw_rules)}")

            # ── Convert ColumnMapping ─────────────────────────────────────────
            for i, r in enumerate(raw_mappings):
                try:
                    mappings.append(from_parser_row(r))
                except Exception as e:
                    st.error(f"ColumnMapping conversion failed at row {i}: {e}")
                    st.code(traceback.format_exc())

            # ── Convert MappingRuleDetail ────────────────────────────────────
            for i, r in enumerate(raw_rules):
                try:
                    rule_details.append(from_rule_row(r))
                except Exception as e:
                    st.error(f"MappingRuleDetail conversion failed at row {i}: {e}")
                    st.code(traceback.format_exc())

            # ── Converted counts ─────────────────────────────────────────────
            st.write(f"**Converted ColumnMapping count:** {len(mappings)}")
            st.write(f"**Converted MappingRuleDetail count:** {len(rule_details)}")

            # ── PHASE 1 VALIDATION (temporary) ────────────────────────────────
            # Confirms the Expression field fix: ColumnMapping.expression should
            # now be populated with real Talend expressions for most rows.
            # Remove once the lineage rebuild (later phases) supersedes this.
            _total_mappings = len(mappings)
            _mappings_with_expr = sum(1 for m in mappings if m.expression)
            st.markdown("**Phase 1 Validation — Expression Field**")
            vcol1, vcol2 = st.columns(2)
            vcol1.metric("Total mappings", _total_mappings)
            vcol2.metric(
                "Mappings with expressions",
                _mappings_with_expr,
                f"{(_mappings_with_expr / _total_mappings * 100):.0f}%" if _total_mappings else "0%",
            )

            # ── First 3 converted objects ─────────────────────────────────────
            st.write("**First 3 ColumnMapping objects:**")
            st.json([vars(m) for m in mappings[:3]] or [])

            st.write("**First 3 MappingRuleDetail objects:**")
            st.json([vars(r) for r in rule_details[:3]] or [])

        except Exception as e:
            import traceback
            st.error(f"column_mapping_service: load failed for '{job_name}': {e}")
            st.code(traceback.format_exc())
            logger.exception(
                "column_mapping_service: failed to load mappings for job '%s' "
                "from path '%s'",
                job_name, item_path,
            )
    else:
        logger.debug(
            "column_mapping_service: no .item file found for job '%s' (path=%r)",
            job_name, item_path,
        )

    # --- Caching temporarily disabled: do not persist results ---
    # st.session_state[cache_key] = {
    #     "mappings":     mappings,
    #     "rule_details": rule_details,
    # }

    return mappings, rule_details


def clear_mapping_cache(job_name: str) -> None:
    """Remove the cached mappings for a job (e.g. after file reload)."""
    key = f"_colmap_{job_name}"
    if key in st.session_state:
        del st.session_state[key]
