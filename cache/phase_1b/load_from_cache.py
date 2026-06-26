#!/usr/bin/env python3
"""
TMA Phase 1B — Load-from-Cache Utility
=======================================
SQLite-backed analysis cache for the Talend Migration Accelerator.
Refresh only when project changes (detected via project_hash).

Tables
------
  project          — scan metadata & project hash
  modules          — all 443 Python modules with source
  sql_analysis     — DDL/DML/PRAGMA/SCHEMA_REF patterns (408 rows)
  java_analysis    — tJava/tJavaRow/tJavaFlex risk analysis (136 rows)
  complexity_scores— per-module component complexity scores (443 rows)
  migration_scores — 7-dimension readiness RAG scores
  repository_summary—repo-level roll-up
  weight_config    — 203 component weights (from complexity_analyzer.py)
  threshold_config — LOW/MEDIUM/HIGH/CRITICAL thresholds
  effort_config    — effort hours per migration type

Usage
-----
    from load_from_cache import Phase1BCache
    cache = Phase1BCache("analysis_cache.db")
    if cache.is_stale(project_base_path):
        # re-run Phase 1B analysis
        pass
    summary  = cache.get_repository_summary()
    scores   = cache.get_migration_scores()
    critical = cache.get_complexity_modules(level="CRITICAL")
    java     = cache.get_java_analysis(risk="HIGH")
    sql      = cache.get_sql_analysis(sql_type="DDL")
"""

from __future__ import annotations
import hashlib, json, os, sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional


class Phase1BCache:
    """Read-only interface to the Phase 1B SQLite analysis cache."""

    def __init__(self, db_path: str = "analysis_cache.db") -> None:
        self.db_path = str(db_path)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ── Staleness detection ───────────────────────────────────────────────────

    def current_project_hash(self, base_path: str) -> str:
        """SHA-256 of all .py file mtimes — matches the stored project_hash."""
        h = hashlib.sha256()
        for p in sorted(Path(base_path).rglob("*.py")):
            try:
                h.update(str(p.stat().st_mtime).encode())
            except OSError:
                pass
        return h.hexdigest()

    def is_stale(self, base_path: str) -> bool:
        """Return True when the project has changed since the cache was built."""
        with self._conn() as conn:
            row = conn.execute("SELECT project_hash FROM project ORDER BY id DESC LIMIT 1").fetchone()
        if row is None:
            return True
        return row["project_hash"] != self.current_project_hash(base_path)

    # ── Data accessors ────────────────────────────────────────────────────────

    def get_project(self) -> dict:
        with self._conn() as conn:
            return dict(conn.execute("SELECT * FROM project").fetchone() or {})

    def get_repository_summary(self) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM repository_summary").fetchone()
            if row is None:
                return {}
            d = dict(row)
            d["top_components"] = json.loads(d.get("top_components") or "{}")
            d["sqlite_cache_tables"] = json.loads(d.get("sqlite_cache_tables") or "[]")
            return d

    def get_migration_scores(self) -> List[dict]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT dimension, score, rag, weight, detail FROM migration_scores ORDER BY weight DESC"
            ).fetchall()]

    def get_complexity_modules(self, level: Optional[str] = None,
                                limit: int = 50) -> List[dict]:
        """Return modules ordered by complexity score, optionally filtered by level."""
        sql = """
            SELECT m.rel_path, m.package, m.lines, cs.score, cs.level,
                   cs.component_count, cs.custom_java_count, cs.db_component_count,
                   cs.tmap_count, cs.risk_factors
            FROM complexity_scores cs JOIN modules m ON cs.module_id = m.id
        """
        params = []
        if level:
            sql += " WHERE cs.level = ?"
            params.append(level.upper())
        sql += " ORDER BY cs.score DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = [dict(r) for r in rows]
        for r in result:
            r["risk_factors"] = json.loads(r["risk_factors"] or "[]")
        return result

    def get_java_analysis(self, risk: Optional[str] = None) -> List[dict]:
        sql = """
            SELECT m.rel_path, ja.component_type, ja.complexity_label,
                   ja.risk_overall, ja.loc, ja.external_jars, ja.risk_findings,
                   ja.has_file_ops, ja.has_jdbc, ja.has_runtime_exec, ja.has_system_env
            FROM java_analysis ja JOIN modules m ON ja.module_id = m.id
        """
        params = []
        if risk:
            sql += " WHERE ja.risk_overall = ?"
            params.append(risk.upper())
        sql += " ORDER BY ja.complexity_score DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = [dict(r) for r in rows]
        for r in result:
            r["external_jars"] = json.loads(r["external_jars"] or "[]")
            r["risk_findings"] = json.loads(r["risk_findings"] or "[]")
        return result

    def get_sql_analysis(self, sql_type: Optional[str] = None,
                          module_path: Optional[str] = None) -> List[dict]:
        sql = """
            SELECT m.rel_path, sa.sql_type, sa.statement, sa.line_number,
                   sa.table_name, sa.db_component
            FROM sql_analysis sa JOIN modules m ON sa.module_id = m.id
        """
        conds, params = [], []
        if sql_type:
            conds.append("sa.sql_type = ?"); params.append(sql_type.upper())
        if module_path:
            conds.append("m.rel_path LIKE ?"); params.append(f"%{module_path}%")
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY m.rel_path, sa.line_number"
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_weight_config(self) -> dict:
        with self._conn() as conn:
            return {r["component_type"]: {"weight": r["weight"], "risk_label": r["risk_label"],
                                           "category": r["category"]}
                    for r in conn.execute("SELECT * FROM weight_config ORDER BY weight DESC").fetchall()}

    def get_module_source(self, rel_path: str) -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT raw_source FROM modules WHERE rel_path = ?", (rel_path,)).fetchone()
        return row["raw_source"] if row else ""

    def stats(self) -> dict:
        with self._conn() as conn:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    for t in ["project","modules","sql_analysis","java_analysis",
                               "complexity_scores","migration_scores","weight_config"]}


if __name__ == "__main__":
    import sys
    db = sys.argv[1] if len(sys.argv) > 1 else "analysis_cache.db"
    base = sys.argv[2] if len(sys.argv) > 2 else "."
    cache = Phase1BCache(db)
    print("Cache stats:", cache.stats())
    print("Stale?", cache.is_stale(base))
    summary = cache.get_repository_summary()
    print(f"Migration readiness: {summary.get('migration_readiness_score')}/100 ({summary.get('migration_rag')})")
    print("Status:", summary.get("migration_status"))
    print("Top 5 complexity CRITICAL modules:")
    for m in cache.get_complexity_modules(level="CRITICAL", limit=5):
        print(f"  [{m['level']}] {m['score']} | {m['rel_path']}")
