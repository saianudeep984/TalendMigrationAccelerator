#!/usr/bin/env python3
"""
TMA Phase 1C — Lineage Cache Loader
=====================================
Loads pre-computed lineage data (Job, Table, Column, Dependencies)
from the Phase 1C lineage cache. No re-analysis required.

Cache Files
-----------
  lineage_cache.json     — full lineage data (job/table/column/dep)
  analysis_cache.db      — Phase 1B SQLite DB (preserved, read-only)

Usage
-----
    from load_lineage_cache import Phase1CLineageCache
    cache = Phase1CLineageCache()

    # Job Lineage
    jobs = cache.get_all_jobs()
    critical = cache.get_jobs_by_complexity("CRITICAL")
    job = cache.get_job("app/analyzers/complexity_analyzer.py")

    # Table Lineage  
    tables = cache.get_all_tables()
    tbl = cache.get_table("jobs")

    # Column Lineage
    col_info = cache.get_column_lineage_info()

    # Dependencies
    deps = cache.get_dependencies("app/lineage/advanced_lineage_engine.py")
    rdeps = cache.get_dependents("app/lineage/lineage_model.py")

    # Summary
    print(cache.summary())
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional


class Phase1CLineageCache:
    """Read-only interface to the Phase 1C lineage cache."""

    def __init__(self, cache_path: str = "lineage_cache.json") -> None:
        self.cache_path = str(cache_path)
        with open(self.cache_path, encoding="utf-8") as f:
            self._data = json.load(f)

    # ── Metadata ─────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        meta = self._data["metadata"]
        scores = self._data["migration_scores"]
        return {
            "phase": meta["phase"],
            "total_modules": meta["total_modules"],
            "total_jobs": meta["total_jobs"],
            "total_components": meta["total_components"],
            "migration_readiness": meta["migration_readiness"],
            "migration_rag": meta["migration_rag"],
            "migration_status": meta["migration_status"],
            "dimension_scores": {s["dimension"]: s["score"] for s in scores},
        }

    def get_migration_scores(self) -> List[dict]:
        return self._data["migration_scores"]

    def get_repository_summary(self) -> dict:
        return self._data["repository_summary"]

    # ── Job Lineage ───────────────────────────────────────────────────────────

    def get_all_jobs(self) -> List[dict]:
        """Return all 443 job/module lineage records."""
        return list(self._data["job_lineage"].values())

    def get_job(self, rel_path: str) -> Optional[dict]:
        """Return lineage record for a specific module path."""
        return self._data["job_lineage"].get(rel_path)

    def get_jobs_by_complexity(self, level: str) -> List[dict]:
        """Filter jobs by complexity level: LOW | MEDIUM | HIGH | CRITICAL."""
        level = level.upper()
        return [j for j in self._data["job_lineage"].values()
                if j.get("complexity_level") == level]

    def get_jobs_by_package(self, package: str) -> List[dict]:
        """Return all jobs in a given package (e.g. 'app.lineage')."""
        return [j for j in self._data["job_lineage"].values()
                if j.get("package") == package]

    def get_jobs_with_tmap(self) -> List[dict]:
        """Return jobs that contain tMap components."""
        return [j for j in self._data["job_lineage"].values()
                if j.get("tmap_count", 0) > 0]

    def get_jobs_with_custom_java(self) -> List[dict]:
        """Return jobs containing custom Java components (tJava/tJavaRow/tJavaFlex)."""
        return [j for j in self._data["job_lineage"].values()
                if j.get("custom_java_count", 0) > 0]

    def get_jobs_with_db_components(self) -> List[dict]:
        """Return jobs that interact with databases."""
        return [j for j in self._data["job_lineage"].values()
                if j.get("db_component_count", 0) > 0]

    # ── Table Lineage ─────────────────────────────────────────────────────────

    def get_all_tables(self) -> List[dict]:
        """Return all table lineage records."""
        return list(self._data["table_lineage"].values())

    def get_table(self, table_name: str) -> Optional[dict]:
        """Return lineage record for a specific table."""
        return self._data["table_lineage"].get(table_name)

    def get_tables_with_ddl(self) -> List[dict]:
        """Return tables that have CREATE/ALTER DDL statements."""
        return [t for t in self._data["table_lineage"].values()
                if t.get("ddl")]

    def get_table_readers(self, table_name: str) -> List[dict]:
        """Return all modules that SELECT from a table."""
        tbl = self._data["table_lineage"].get(table_name, {})
        return tbl.get("reads", [])

    def get_table_writers(self, table_name: str) -> List[dict]:
        """Return all modules that INSERT/UPDATE/DELETE into a table."""
        tbl = self._data["table_lineage"].get(table_name, {})
        return tbl.get("writes", [])

    # ── Column Lineage ────────────────────────────────────────────────────────

    def get_column_lineage_info(self) -> dict:
        """
        Return column lineage metadata. Column-level lineage is computed
        at runtime by AdvancedLineageEngine — this cache contains the
        engine locations, field schemas, and architectural description.
        """
        return self._data["column_lineage"]

    def get_lineage_engine_modules(self) -> List[str]:
        """Return paths to all lineage engine source files."""
        cl = self._data["column_lineage"]
        return [v for k, v in cl.items()
                if k not in ("description", "node_types", "edge_types",
                             "transformation_types", "physical_resolution",
                             "cross_job_bridging", "column_level_fields")]

    # ── Dependencies ──────────────────────────────────────────────────────────

    def get_dependencies(self, rel_path: str) -> List[str]:
        """Return internal app.* packages imported by this module."""
        return self._data["dependency_graph"].get(rel_path, {}).get("imports", [])

    def get_dependents(self, rel_path: str) -> List[str]:
        """Return modules that import this module."""
        return self._data["dependency_graph"].get(rel_path, {}).get("imported_by", [])

    def get_dependency_record(self, rel_path: str) -> Optional[dict]:
        """Full dependency record for a module."""
        return self._data["dependency_graph"].get(rel_path)

    def get_all_packages(self) -> List[str]:
        """Return sorted list of all distinct package names."""
        return sorted(set(
            v["package"] for v in self._data["dependency_graph"].values()
        ))

    def get_isolated_modules(self) -> List[str]:
        """Return modules with no internal imports and no dependents."""
        return [path for path, rec in self._data["dependency_graph"].items()
                if not rec["imports"] and not rec["imported_by"]]


if __name__ == "__main__":
    cache = Phase1CLineageCache()
    s = cache.summary()
    print(f"TMA Phase 1C Lineage Cache")
    print(f"  Modules  : {s['total_modules']}")
    print(f"  Readiness: {s['migration_readiness']}/100 ({s['migration_rag']})")
    print(f"  Status   : {s['migration_status']}")
    print()
    print("Complexity breakdown:")
    for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        jobs = cache.get_jobs_by_complexity(level)
        print(f"  {level}: {len(jobs)} modules")
    print()
    print(f"Tables with lineage: {len(cache.get_all_tables())}")
    print(f"Tables with DDL    : {len(cache.get_tables_with_ddl())}")
    print(f"Jobs with tMap     : {len(cache.get_jobs_with_tmap())}")
    print(f"Jobs with Java     : {len(cache.get_jobs_with_custom_java())}")
    print()
    print("Dimension scores:")
    for dim, score in s["dimension_scores"].items():
        print(f"  {dim}: {score}")
