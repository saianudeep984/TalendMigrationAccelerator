#!/usr/bin/env python3
"""
TMA Phase 1D — Search Index
============================
SQLite-backed search index for Jobs, Tables, Columns, SQL, Java, Components.
No repository scan required — all data is pre-indexed.

Index Tables
------------
  idx_jobs        — 443 modules with complexity/risk metadata
  idx_tables      — 63 table-level SQL rows (DDL/DML/SCHEMA_REF)
  idx_columns     — 40 column-level lineage rows (source/target/expression)
  idx_sql         — 408 SQL statements (full text)
  idx_java        — 136 Java component rows (tJava/tJavaRow/tJavaFlex)
  idx_components  — 203 component types with weights/risk labels
  idx_meta        — index metadata and migration scores

FTS5 Tables (full-text search)
-------------------------------
  fts_jobs        — rel_path, module_name, package, complexity_level, risk_factors
  fts_sql         — rel_path, sql_type, statement, table_name, db_component
  fts_java        — rel_path, component_type, risk_overall, risk_findings
  fts_components  — rel_path, component_type, category, risk_label

Usage
-----
    from search import TMASearchIndex
    idx = TMASearchIndex()

    # Jobs
    idx.search_jobs("lineage")                    # FTS
    idx.get_jobs_by_level("CRITICAL")             # B-tree
    idx.get_jobs_by_package("app.lineage")        # B-tree
    idx.get_job("app/lineage/lineage_model.py")   # exact

    # Tables
    idx.search_tables("jobs")
    idx.get_table_ddl()
    idx.get_tables_for_module("cache_manager")

    # Columns
    idx.search_columns(source_table="CUSTOMERS")
    idx.get_columns_for_job("app/lineage/lineage_graph_builder.py")

    # SQL
    idx.search_sql("SELECT * FROM jobs")
    idx.get_sql_by_type("DDL")

    # Java
    idx.search_java("tJavaFlex")
    idx.get_java_by_risk("HIGH")
    idx.get_java_with_jdbc()

    # Components
    idx.search_components("tMap")
    idx.get_components_by_category("TRANSFORM")
    idx.top_components(n=10)

    # Summary
    idx.summary()
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import List, Optional


class TMASearchIndex:
    """Read-only search interface over the Phase 1D SQLite index."""

    def __init__(self, db_path: str = "search_index.db") -> None:
        self.db_path = str(db_path)

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def _rows(self, sql, params=()):
        with self._conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    # ── Metadata ──────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        with self._conn() as c:
            meta = {r['key']: r['value'] for r in c.execute('SELECT key,value FROM idx_meta').fetchall()}
        return {
            'phase': meta.get('phase'),
            'total_modules': int(meta.get('total_modules', 0)),
            'total_jobs': int(meta.get('total_jobs', 0)),
            'total_components': int(meta.get('total_components', 0)),
            'total_sql_rows': int(meta.get('total_sql_rows', 0)),
            'total_java_rows': int(meta.get('total_java_rows', 0)),
            'total_column_rows': int(meta.get('total_column_rows', 0)),
            'total_component_types': int(meta.get('total_component_types', 0)),
            'migration_readiness': int(meta.get('migration_readiness', 0)),
            'migration_rag': meta.get('migration_rag'),
            'migration_status': meta.get('migration_status'),
            'migration_scores': json.loads(meta.get('migration_scores', '[]')),
            'index_tables': json.loads(meta.get('index_tables', '[]')),
            'fts_tables': json.loads(meta.get('fts_tables', '[]')),
        }

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def search_jobs(self, query: str, limit: int = 20) -> List[dict]:
        """Full-text search across job rel_path, module_name, package, risk_factors."""
        return self._rows(
            'SELECT j.* FROM fts_jobs f JOIN idx_jobs j ON f.rowid=j.id '
            'WHERE fts_jobs MATCH ? ORDER BY rank LIMIT ?', (query, limit))

    def get_job(self, rel_path: str) -> Optional[dict]:
        rows = self._rows('SELECT * FROM idx_jobs WHERE rel_path=?', (rel_path,))
        return rows[0] if rows else None

    def get_jobs_by_level(self, level: str, limit: int = 100) -> List[dict]:
        return self._rows(
            'SELECT * FROM idx_jobs WHERE complexity_level=? ORDER BY complexity_score DESC LIMIT ?',
            (level.upper(), limit))

    def get_jobs_by_package(self, package: str) -> List[dict]:
        return self._rows('SELECT * FROM idx_jobs WHERE package=? ORDER BY rel_path', (package,))

    def get_top_jobs_by_score(self, n: int = 20) -> List[dict]:
        return self._rows('SELECT * FROM idx_jobs ORDER BY complexity_score DESC LIMIT ?', (n,))

    def get_jobs_with_tmap(self) -> List[dict]:
        return self._rows('SELECT * FROM idx_jobs WHERE tmap_count>0 ORDER BY tmap_count DESC')

    def get_jobs_with_java(self) -> List[dict]:
        return self._rows('SELECT * FROM idx_jobs WHERE custom_java_count>0 ORDER BY custom_java_count DESC')

    def get_jobs_with_db(self) -> List[dict]:
        return self._rows('SELECT * FROM idx_jobs WHERE db_component_count>0 ORDER BY db_component_count DESC')

    def jobs_complexity_summary(self) -> dict:
        with self._conn() as c:
            return {r['complexity_level']: r['cnt'] for r in c.execute(
                'SELECT complexity_level, COUNT(*) cnt FROM idx_jobs GROUP BY complexity_level'
            ).fetchall()}

    # ── Tables ────────────────────────────────────────────────────────────────

    def search_tables(self, query: str, limit: int = 20) -> List[dict]:
        return self._rows(
            'SELECT * FROM idx_tables WHERE table_name LIKE ? ORDER BY table_name LIMIT ?',
            (f'%{query}%', limit))

    def get_table_ddl(self) -> List[dict]:
        return self._rows("SELECT DISTINCT table_name, statement, rel_path FROM idx_tables WHERE sql_type='DDL' ORDER BY table_name")

    def get_tables_for_module(self, module_fragment: str) -> List[dict]:
        return self._rows('SELECT * FROM idx_tables WHERE rel_path LIKE ? ORDER BY table_name',
                          (f'%{module_fragment}%',))

    def get_distinct_tables(self) -> List[str]:
        return [r['table_name'] for r in self._rows(
            'SELECT DISTINCT table_name FROM idx_tables WHERE table_name IS NOT NULL ORDER BY table_name')]

    # ── Columns ───────────────────────────────────────────────────────────────

    def search_columns(self, source_table: Optional[str] = None,
                       target_table: Optional[str] = None,
                       column_name: Optional[str] = None) -> List[dict]:
        conds, params = [], []
        if source_table:
            conds.append('source_table LIKE ?'); params.append(f'%{source_table}%')
        if target_table:
            conds.append('target_table LIKE ?'); params.append(f'%{target_table}%')
        if column_name:
            conds.append('(source_column LIKE ? OR target_column LIKE ?)');
            params += [f'%{column_name}%', f'%{column_name}%']
        sql = 'SELECT * FROM idx_columns'
        if conds:
            sql += ' WHERE ' + ' AND '.join(conds)
        sql += ' ORDER BY job_rel_path LIMIT 200'
        return self._rows(sql, params)

    def get_columns_for_job(self, rel_path: str) -> List[dict]:
        return self._rows('SELECT * FROM idx_columns WHERE job_rel_path=?', (rel_path,))

    # ── SQL ───────────────────────────────────────────────────────────────────

    def search_sql(self, query: str, limit: int = 30) -> List[dict]:
        """FTS search across SQL statements, table names, db_component."""
        return self._rows(
            'SELECT s.* FROM fts_sql f JOIN idx_sql s ON f.rowid=s.id '
            'WHERE fts_sql MATCH ? ORDER BY rank LIMIT ?', (query, limit))

    def get_sql_by_type(self, sql_type: str) -> List[dict]:
        return self._rows('SELECT * FROM idx_sql WHERE sql_type=? ORDER BY rel_path,line_number',
                          (sql_type.upper(),))

    def get_sql_for_module(self, rel_path: str) -> List[dict]:
        return self._rows('SELECT * FROM idx_sql WHERE rel_path=? ORDER BY line_number', (rel_path,))

    def sql_type_summary(self) -> dict:
        with self._conn() as c:
            return {r['sql_type']: r['cnt'] for r in c.execute(
                'SELECT sql_type, COUNT(*) cnt FROM idx_sql GROUP BY sql_type'
            ).fetchall()}

    # ── Java ──────────────────────────────────────────────────────────────────

    def search_java(self, query: str, limit: int = 20) -> List[dict]:
        return self._rows(
            'SELECT j.* FROM fts_java f JOIN idx_java j ON f.rowid=j.id '
            'WHERE fts_java MATCH ? ORDER BY rank LIMIT ?', (query, limit))

    def get_java_by_risk(self, risk: str) -> List[dict]:
        return self._rows('SELECT * FROM idx_java WHERE risk_overall=? ORDER BY loc DESC',
                          (risk.upper(),))

    def get_java_with_jdbc(self) -> List[dict]:
        return self._rows("SELECT * FROM idx_java WHERE has_jdbc=1 ORDER BY rel_path")

    def get_java_with_file_ops(self) -> List[dict]:
        return self._rows("SELECT * FROM idx_java WHERE has_file_ops=1 ORDER BY rel_path")

    def get_java_with_runtime_exec(self) -> List[dict]:
        return self._rows("SELECT * FROM idx_java WHERE has_runtime_exec=1 ORDER BY rel_path")

    def java_risk_summary(self) -> dict:
        with self._conn() as c:
            return {r['risk_overall']: r['cnt'] for r in c.execute(
                'SELECT risk_overall, COUNT(*) cnt FROM idx_java GROUP BY risk_overall'
            ).fetchall()}

    # ── Components ────────────────────────────────────────────────────────────

    def search_components(self, query: str, limit: int = 20) -> List[dict]:
        return self._rows(
            'SELECT c.* FROM fts_components f JOIN idx_components c ON f.rowid=c.id '
            'WHERE fts_components MATCH ? ORDER BY rank LIMIT ?', (query, limit))

    def get_components_by_category(self, category: str) -> List[dict]:
        return self._rows('SELECT * FROM idx_components WHERE category=? ORDER BY weight DESC',
                          (category,))

    def top_components(self, n: int = 10) -> List[dict]:
        return self._rows('SELECT * FROM idx_components ORDER BY count_in_repo DESC, weight DESC LIMIT ?', (n,))

    def get_component(self, component_type: str) -> Optional[dict]:
        rows = self._rows('SELECT * FROM idx_components WHERE component_type=?', (component_type,))
        return rows[0] if rows else None

    def component_category_summary(self) -> dict:
        with self._conn() as c:
            return {r['category']: r['cnt'] for r in c.execute(
                'SELECT category, COUNT(*) cnt FROM idx_components GROUP BY category ORDER BY cnt DESC'
            ).fetchall()}


if __name__ == '__main__':
    idx = TMASearchIndex()
    s = idx.summary()
    print('TMA Phase 1D — Search Index')
    print(f"  Modules     : {s['total_modules']}")
    print(f"  SQL rows    : {s['total_sql_rows']}")
    print(f"  Java rows   : {s['total_java_rows']}")
    print(f"  Column rows : {s['total_column_rows']}")
    print(f"  Comp types  : {s['total_component_types']}")
    print(f"  Readiness   : {s['migration_readiness']}/100 ({s['migration_rag']})")
    print()
    print('Complexity:', idx.jobs_complexity_summary())
    print('Java risk :', idx.java_risk_summary())
    print('SQL types :', idx.sql_type_summary())
    print('Top 5 components:')
    for c in idx.top_components(5):
        print(f"  {c['component_type']}: {c['count_in_repo']} (weight={c['weight']}, {c['category']})")
    print()
    print('FTS: jobs MATCH "lineage":')
    for j in idx.search_jobs('lineage', limit=3):
        print(f"  [{j['complexity_level']}] {j['rel_path']}")
    print('FTS: sql MATCH "CREATE":')
    for r in idx.search_sql('CREATE', limit=3):
        print(f"  {r['rel_path']}:{r['line_number']} -> {r['table_name']}")
