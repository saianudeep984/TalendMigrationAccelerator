"""Cached lineage views backed by cache/phase_1c/lineage_cache.json.

This module intentionally reads the Phase 1C cache only. It does not parse
Talend XML, scan the repository, or rebuild lineage graphs.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    import streamlit as st
except ImportError:
    import types as _types

    class _StubCtx:
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def __getattr__(self, name): return lambda *args, **kwargs: None

    def _cache_data(*args, **kwargs):
        if args and callable(args[0]):
            return args[0]
        return lambda fn: fn

    st = _types.SimpleNamespace(
        cache_data=_cache_data,
        caption=lambda *args, **kwargs: None,
        columns=lambda n, **kwargs: [_StubCtx() for _ in range(n if isinstance(n, int) else len(n))],
        dataframe=lambda *args, **kwargs: None,
        error=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        markdown=lambda *args, **kwargs: None,
        metric=lambda *args, **kwargs: None,
        radio=lambda *args, **kwargs: None,
        selectbox=lambda *args, **kwargs: None,
    )

try:
    import pandas as pd
except ImportError:
    class _PandasFallback:
        @staticmethod
        def DataFrame(data=None, *args, **kwargs):
            return data or []

    pd = _PandasFallback()


_CACHE_PATH = os.path.join("cache", "phase_1c", "lineage_cache.json")


@st.cache_data(show_spinner=False)
def load_cached_lineage(cache_path: str = _CACHE_PATH) -> dict:
    with open(cache_path, encoding="utf-8") as f:
        return json.load(f)


def _rows(items: list[Any], key: str = "Value") -> pd.DataFrame:
    if not items:
        return pd.DataFrame({key: []})
    if isinstance(items[0], dict):
        return pd.DataFrame(items)
    return pd.DataFrame({key: items})


def _table_modules(table: dict) -> set[str]:
    modules = set(table.get("modules", []) or [])
    for bucket in ("reads", "writes", "ddl"):
        for rec in table.get(bucket, []) or []:
            module = rec.get("module")
            if module:
                modules.add(module)
    return modules


def related_tables(data: dict, module: str) -> list[dict]:
    tables = []
    for table in data.get("table_lineage", {}).values():
        if module in _table_modules(table):
            reads = [r for r in table.get("reads", []) if r.get("module") == module]
            writes = [r for r in table.get("writes", []) if r.get("module") == module]
            ddl = [r for r in table.get("ddl", []) if r.get("module") == module]
            tables.append({
                "Table": table.get("table_name", ""),
                "Reads": len(reads),
                "Writes": len(writes),
                "DDL": len(ddl),
                "Access": ", ".join(
                    label for label, count in (("read", reads), ("write", writes), ("ddl", ddl)) if count
                ) or "referenced",
            })
    return sorted(tables, key=lambda r: r["Table"])


def _tables_read_by_module(data: dict, module: str) -> set[str]:
    tables = set()
    for table in data.get("table_lineage", {}).values():
        if any(r.get("module") == module for r in table.get("reads", []) or []):
            tables.add(table.get("table_name", ""))
    return {t for t in tables if t}


def _tables_written_by_module(data: dict, module: str) -> set[str]:
    tables = set()
    for table in data.get("table_lineage", {}).values():
        if any(r.get("module") == module for r in table.get("writes", []) or []):
            tables.add(table.get("table_name", ""))
    return {t for t in tables if t}


def _table_writers(data: dict, table_name: str) -> set[str]:
    table = data.get("table_lineage", {}).get(table_name, {})
    return {r.get("module", "") for r in table.get("writes", []) or [] if r.get("module")}


def _table_readers(data: dict, table_name: str) -> set[str]:
    table = data.get("table_lineage", {}).get(table_name, {})
    return {r.get("module", "") for r in table.get("reads", []) or [] if r.get("module")}


def upstream_jobs(data: dict, module: str) -> list[str]:
    dep = data.get("dependency_graph", {}).get(module, {})
    upstream = set(dep.get("imports", []) or [])
    for table in _tables_read_by_module(data, module):
        upstream.update(_table_writers(data, table))
    upstream.discard(module)
    return sorted(upstream)


def downstream_jobs(data: dict, module: str) -> list[str]:
    dep = data.get("dependency_graph", {}).get(module, {})
    downstream = set(dep.get("imported_by", []) or [])
    for table in _tables_written_by_module(data, module):
        downstream.update(_table_readers(data, table))
    downstream.discard(module)
    return sorted(downstream)


def _columns_from_statement(statement: str, table_name: str = "") -> set[str]:
    sql = re.sub(r"\s+", " ", str(statement or "")).strip()
    columns: set[str] = set()

    select_match = re.search(r"\bSELECT\s+(.+?)\s+\bFROM\b", sql, flags=re.IGNORECASE)
    if select_match:
        for raw in select_match.group(1).split(","):
            col = re.sub(r"\s+AS\s+.*$", "", raw.strip(), flags=re.IGNORECASE)
            col = col.split(".")[-1].strip('"[]` ')
            if col and col != "*" and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", col):
                columns.add(f"{table_name}.{col}" if table_name else col)

    insert_match = re.search(r"\bINSERT\s+INTO\s+[A-Za-z0-9_.\[\]\"`]+\s*\((.+?)\)", sql, flags=re.IGNORECASE)
    if insert_match:
        for raw in insert_match.group(1).split(","):
            col = raw.strip('"[]` ')
            if col:
                columns.add(f"{table_name}.{col}" if table_name else col)

    update_match = re.search(r"\bSET\s+(.+?)(?:\s+\bWHERE\b|$)", sql, flags=re.IGNORECASE)
    if update_match:
        for raw in update_match.group(1).split(","):
            col = raw.split("=", 1)[0].strip().split(".")[-1].strip('"[]` ')
            if col:
                columns.add(f"{table_name}.{col}" if table_name else col)

    return columns


def affected_columns(data: dict, module: str) -> list[str]:
    columns: set[str] = set()
    job = data.get("job_lineage", {}).get(module, {})
    for op in job.get("sql_operations", []) or []:
        columns.update(_columns_from_statement(op.get("statement", ""), op.get("table_name", "")))

    for table in data.get("table_lineage", {}).values():
        table_name = table.get("table_name", "")
        for bucket in ("reads", "writes", "ddl"):
            for rec in table.get(bucket, []) or []:
                if rec.get("module") == module:
                    columns.update(_columns_from_statement(rec.get("statement", ""), table_name))
    return sorted(columns)


def _default_module(data: dict, preferred_name: str | None = None) -> tuple[str, bool]:
    """Return (module_key, matched) where matched=True if preferred_name was found in the cache."""
    jobs = data.get("job_lineage", {})
    if preferred_name:
        needle = preferred_name.lower()
        # 1. Exact key match (handles cases where cache keys are already Talend job names)
        for module in jobs:
            if module.lower() == needle:
                return module, True
        # 2. module_name field exact match (e.g. cache record has "module_name": "SC_AS400_To_DropZone_MD")
        for module, rec in jobs.items():
            if str(rec.get("module_name", "")).lower() == needle:
                return module, True
        # 3. Talend job name embedded in path  (e.g. "process/SupplyChain_Phase6_1/SC_AS400_To_DropZone_MD_3.1")
        for module, rec in jobs.items():
            base = re.sub(r"_\d+\.\d+$", "", module.split("/")[-1]).lower()
            if base == needle:
                return module, True
        # 4. Partial/substring match on key basename
        for module in jobs:
            if needle in module.lower():
                return module, True
        # No match found — fall back but signal the caller
        critical = [m for m, r in jobs.items() if r.get("complexity_level") == "CRITICAL"]
        fallback = sorted(critical or jobs.keys())[0] if jobs else ""
        return fallback, False
    critical = [m for m, r in jobs.items() if r.get("complexity_level") == "CRITICAL"]
    return (sorted(critical or jobs.keys())[0] if jobs else ""), True


def _kpi(label: str, value: Any, caption: str = "") -> None:
    st.metric(label, value, caption)


def _module_picker(data: dict, key: str, preferred_name: str | None = None) -> str:
    modules = sorted(data.get("job_lineage", {}).keys())
    if not modules:
        return ""
    default, matched = _default_module(data, preferred_name)
    if preferred_name and not matched:
        st.warning(
            f"⚠️ Job **{preferred_name}** was not found in the Phase 1C lineage cache. "
            "The cache appears to contain entries for a different project or file set "
            "(e.g. Python source files instead of Talend `.item` jobs). "
            "Please regenerate the lineage cache from the Talend repository. "
            "Showing all available cache entries below."
        )
    index = modules.index(default) if default in modules else 0
    return st.selectbox("Select Job / Module", modules, index=index, key=key)


def _render_job_lineage(data: dict, module: str) -> None:
    rec = data.get("job_lineage", {}).get(module, {})
    up = upstream_jobs(data, module)
    down = downstream_jobs(data, module)
    tables = related_tables(data, module)
    columns = affected_columns(data, module)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _kpi("Upstream Jobs", len(up), "imports and table writers")
    with k2:
        _kpi("Downstream Jobs", len(down), "dependents and table readers")
    with k3:
        _kpi("Affected Tables", len(tables), "cached table lineage")
    with k4:
        _kpi("Affected Columns", len(columns), "derived from cached SQL")

    st.markdown("##### Job Lineage")
    st.dataframe(pd.DataFrame([{
        "Job": module,
        "Package": rec.get("package", ""),
        "Complexity": rec.get("complexity_level", ""),
        "Components": rec.get("component_count", 0),
        "tMap": rec.get("tmap_count", 0),
        "DB Components": rec.get("db_component_count", 0),
        "Custom Java": rec.get("custom_java_count", 0),
    }]), use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Upstream Jobs")
        st.dataframe(_rows(up, "Upstream Job"), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("##### Downstream Jobs")
        st.dataframe(_rows(down, "Downstream Job"), use_container_width=True, hide_index=True)

    st.markdown("##### Affected Tables")
    st.dataframe(_rows(tables), use_container_width=True, hide_index=True)

    st.markdown("##### Affected Columns")
    if columns:
        st.dataframe(_rows(columns, "Affected Column"), use_container_width=True, hide_index=True)
    else:
        st.caption("No concrete column names are present in the cached SQL statements for this module.")


def _render_table_lineage(data: dict, widget_key: str = "_cached_lineage_module") -> None:
    tables = sorted(data.get("table_lineage", {}).keys())
    if not tables:
        st.info("No cached table lineage available.")
        return
    table_name = st.selectbox("Select Table", tables, key=f"{widget_key}_table")
    table = data["table_lineage"][table_name]
    readers = table.get("reads", []) or []
    writers = table.get("writes", []) or []
    ddl = table.get("ddl", []) or []

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _kpi("Readers", len(readers))
    with k2:
        _kpi("Writers", len(writers))
    with k3:
        _kpi("DDL Statements", len(ddl))
    with k4:
        _kpi("Affected Jobs", len(_table_modules(table)))

    st.markdown("##### Table Lineage")
    st.dataframe(pd.DataFrame([{
        "Table": table_name,
        "Affected Jobs": ", ".join(sorted(_table_modules(table))) or "-",
    }]), use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Upstream Jobs")
        st.dataframe(_rows(sorted(_table_writers(data, table_name)), "Writer Job"), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("##### Downstream Jobs")
        st.dataframe(_rows(sorted(_table_readers(data, table_name)), "Reader Job"), use_container_width=True, hide_index=True)

    st.markdown("##### Read Operations")
    st.dataframe(_rows(readers), use_container_width=True, hide_index=True)
    st.markdown("##### Write Operations")
    st.dataframe(_rows(writers), use_container_width=True, hide_index=True)


def _render_column_lineage(data: dict, module: str) -> None:
    col_info = data.get("column_lineage", {})
    columns = affected_columns(data, module)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _kpi("Affected Columns", len(columns))
    with k2:
        _kpi("Node Types", len(col_info.get("node_types", []) or []))
    with k3:
        _kpi("Edge Types", len(col_info.get("edge_types", []) or []))
    with k4:
        _kpi("Transforms", len(col_info.get("transformation_types", []) or []))

    st.markdown("##### Column Lineage")
    if columns:
        st.dataframe(_rows(columns, "Affected Column"), use_container_width=True, hide_index=True)
    else:
        st.caption("The Phase 1C cache has column-lineage engine metadata, but no row-level column edges for this selected module.")

    st.markdown("##### Cached Column Lineage Metadata")
    st.dataframe(pd.DataFrame([
        {"Area": "Node Types", "Values": ", ".join(col_info.get("node_types", []) or [])},
        {"Area": "Edge Types", "Values": ", ".join(col_info.get("edge_types", []) or [])},
        {"Area": "Transformation Types", "Values": ", ".join(col_info.get("transformation_types", []) or [])},
        {"Area": "Physical Resolution", "Values": col_info.get("physical_resolution", "")},
        {"Area": "Cross-job Bridging", "Values": col_info.get("cross_job_bridging", "")},
    ]), use_container_width=True, hide_index=True)

    fields = col_info.get("column_level_fields", {}) or {}
    if fields:
        st.markdown("##### Column Lineage Field Schema")
        st.dataframe(
            pd.DataFrame([{"Group": k, "Fields": ", ".join(v)} for k, v in fields.items()]),
            use_container_width=True,
            hide_index=True,
        )


def _render_dependency_lineage(data: dict, module: str) -> None:
    dep = data.get("dependency_graph", {}).get(module, {})
    imports = dep.get("imports", []) or []
    imported_by = dep.get("imported_by", []) or []

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _kpi("Upstream Jobs", len(imports), "internal imports")
    with k2:
        _kpi("Downstream Jobs", len(imported_by), "imported by")
    with k3:
        _kpi("Dependency Lineage", len(imports) + len(imported_by), "cached edges")
    with k4:
        _kpi("Package", dep.get("package", "-"))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Upstream Jobs")
        st.dataframe(_rows(imports, "Imported Module"), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("##### Downstream Jobs")
        st.dataframe(_rows(imported_by, "Dependent Module"), use_container_width=True, hide_index=True)


def _render_impact(data: dict, module: str) -> None:
    up = upstream_jobs(data, module)
    down = downstream_jobs(data, module)
    tables = related_tables(data, module)
    columns = affected_columns(data, module)
    rec = data.get("job_lineage", {}).get(module, {})
    risk_factors = rec.get("risk_factors", []) or []

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _kpi("Upstream Jobs", len(up))
    with k2:
        _kpi("Downstream Jobs", len(down))
    with k3:
        _kpi("Affected Tables", len(tables))
    with k4:
        _kpi("Affected Columns", len(columns))

    st.markdown("##### Impact Analysis")
    st.dataframe(pd.DataFrame([{
        "Selected Job": module,
        "Complexity": rec.get("complexity_level", ""),
        "Complexity Score": rec.get("complexity_score", 0),
        "Risk Factors": len(risk_factors),
        "Blast Radius": len(up) + len(down) + len(tables) + len(columns),
    }]), use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Affected Tables")
        st.dataframe(_rows(tables), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("##### Affected Columns")
        st.dataframe(_rows(columns, "Affected Column"), use_container_width=True, hide_index=True)

    if risk_factors:
        st.markdown("##### Risk Drivers")
        st.dataframe(_rows(risk_factors, "Risk Factor"), use_container_width=True, hide_index=True)


def _detect_cache_source_mismatch(data: dict) -> str | None:
    """Return an error message if the cache appears to contain Python source files
    instead of Talend job entries, otherwise return None.

    The check samples up to 20 job_lineage keys. If the majority look like Python
    module paths (end in .py, contain typical Python package separators, or start
    with 'app/') the cache is considered mismatched.
    """
    jobs = data.get("job_lineage", {})
    if not jobs:
        return None
    sample = list(jobs.keys())[:20]
    python_indicators = sum(
        1 for k in sample
        if k.endswith(".py")
        or k.startswith("app/")
        or re.search(r"/[a-z_]+/__init__", k)
    )
    if python_indicators >= len(sample) // 2:
        example_keys = ", ".join(f"`{k}`" for k in sample[:3])
        return (
            "🚨 **Cache source mismatch detected.** "
            "The Phase 1C lineage cache appears to have been built from "
            "**Python source files** (TMA application code) rather than "
            "**Talend `.item` job files**. "
            f"Example cache keys: {example_keys}. "
            "\n\n**To fix:** regenerate the Phase 1C lineage cache by pointing the "
            "cache builder at your Talend repository directory "
            "(`temp_repository/<PROJECT>/process/`) so that `job_lineage` keys "
            "match Talend job names (e.g. `SC_AS400_To_DropZone_MD`). "
            "Column Lineage and Lineage views will show Python module data until the cache is rebuilt."
        )
    return None


def _clear_stale_lineage_cache() -> None:
    """Delete the on-disk lineage cache and clear Streamlit's in-memory cache."""
    import os
    try:
        if os.path.exists(_CACHE_PATH):
            os.remove(_CACHE_PATH)
    except OSError:
        pass
    try:
        load_cached_lineage.clear()
    except Exception:
        pass


def render_cached_lineage_page(preferred_job_name: str | None = None, default_view: str = "Job Lineage", widget_key: str = "_cached_lineage_module") -> None:
    import os as _os
    if not _os.path.exists(_CACHE_PATH):
        st.info("Column Lineage requires the Phase 1C cache. Run `build_phase1c_lineage_cache.py` against your repository to enable this view.")
        return

    try:
        data = load_cached_lineage()
    except Exception:
        st.info("Column Lineage requires the Phase 1C cache. Run `build_phase1c_lineage_cache.py` against your repository to enable this view.")
        return

    # ── Sanity-check 1: cache built from Python files instead of Talend .item jobs ──
    mismatch_msg = _detect_cache_source_mismatch(data)
    if mismatch_msg:
        _clear_stale_lineage_cache()
        st.info("Column Lineage requires the Phase 1C cache. Run `build_phase1c_lineage_cache.py` against your repository to enable this view.")
        return

    # ── Sanity-check 2: cache exists but doesn't contain the currently loaded jobs ──
    if preferred_job_name:
        cache_jobs = set(data.get("job_lineage", {}).keys())
        loaded_jobs = {
            j["job_data"]["job_name"]
            for j in (st.session_state.get("last_analysis_jobs") or [])
            if isinstance(j, dict) and "job_data" in j
        }
        # If loaded jobs are Talend-style names but cache has none of them → stale
        if loaded_jobs and cache_jobs and not loaded_jobs.intersection(cache_jobs):
            _clear_stale_lineage_cache()
            st.info(
                "Lineage cache was from a previous repository and has been cleared. "
                "Re-run analysis to rebuild lineage for the current repository."
            )
            return

    meta = data.get("metadata", {})
    st.caption(
        "Using cached Phase 1C lineage only. "
        f"Modules: {meta.get('total_modules', 0)} | Components: {meta.get('total_components', 0)} | "
        f"Readiness: {meta.get('migration_readiness', '-')}/100 ({meta.get('migration_rag', '-')})"
    )

    module = _module_picker(data, widget_key, preferred_job_name)
    if not module:
        st.info("No cached job lineage available.")
        return

    views = ["Job Lineage", "Table Lineage", "Column Lineage", "Dependency Lineage", "Impact Analysis"]
    index = views.index(default_view) if default_view in views else 0
    view = st.radio("Cached Lineage View", views, index=index, horizontal=True, key=f"{widget_key}_view")

    if view == "Job Lineage":
        _render_job_lineage(data, module)
    elif view == "Table Lineage":
        _render_table_lineage(data, widget_key)
    elif view == "Column Lineage":
        _render_column_lineage(data, module)
    elif view == "Dependency Lineage":
        _render_dependency_lineage(data, module)
    else:
        _render_impact(data, module)
