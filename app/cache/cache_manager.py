"""
cache_manager.py
================
SQLite-backed persistent cache for the Talend Migration Accelerator.

Eliminates repeated XML parsing by storing parsed job metadata on first
access and serving it from cache on subsequent reads.

Cached entities
---------------
  jobs        – full extract_job_info() dict per .item file
  components  – flattened component rows (unique_name, type, parameters)
  sources     – source-component rows (from source_target_extractor)
  targets     – target-component rows (from source_target_extractor)
  mappings    – column-mapping rows (from extract_column_mappings)

Public API
----------
  CacheManager(db_path)          – open (or create) the cache database
  cm.get_job(file_path)          – return cached job_info or None
  cm.put_job(file_path, data)    – persist a parsed job and its sub-entities
  cm.get_all_jobs()              – return all cached job_info dicts
  cm.is_stale(file_path)         – True when mtime changed since last cache
  cm.invalidate(file_path)       – remove one job from cache
  cm.clear()                     – wipe the entire cache
  cm.stats()                     – row counts for every table
  cm.load_or_parse(file_path)    – high-level: cache-hit or parse + cache

Staleness detection
-------------------
Each cached job stores the file's mtime (float) at parse time.
is_stale() compares the stored mtime against the current mtime on disk;
if they differ the cache entry is automatically refreshed by load_or_parse.

Usage example
-------------
    from app.cache.cache_manager import CacheManager
    from app.parser.talend_xml_parser import TalendJobParser

    cm = CacheManager()                              # default: tma_cache.db
    job_data = cm.load_or_parse("/path/to/job.item")
    all_jobs = cm.get_all_jobs()
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default cache location – next to the project root, or a temp dir
# ---------------------------------------------------------------------------
_DEFAULT_DB_NAME = "tma_cache.db"
_DEFAULT_DB_PATH = os.path.join(
    os.environ.get("TMA_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "cache")),
    _DEFAULT_DB_NAME,
)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;

-- One row per .item file
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path   TEXT    NOT NULL UNIQUE,
    file_hash   TEXT    NOT NULL,      -- SHA-256 of raw file bytes
    file_mtime  REAL    NOT NULL,      -- os.path.getmtime() at parse time
    job_name    TEXT    NOT NULL,
    job_version TEXT,
    talend_version TEXT,
    raw_json    TEXT    NOT NULL,      -- full extract_job_info() JSON blob
    cached_at   REAL    NOT NULL       -- unix timestamp when cached
);

-- Flattened component rows (1 job → N components)
CREATE TABLE IF NOT EXISTS components (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    unique_name     TEXT,
    component_type  TEXT,
    parameters_json TEXT               -- serialised parameters dict
);

-- Source components resolved by source_target_extractor
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name            TEXT,
    component_type  TEXT,
    unique_name     TEXT,
    purpose         TEXT,
    qualified_name  TEXT,
    db_type         TEXT,
    physical_ref_json TEXT             -- PhysicalTableRef as JSON
);

-- Target components resolved by source_target_extractor
CREATE TABLE IF NOT EXISTS targets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name            TEXT,
    component_type  TEXT,
    unique_name     TEXT,
    purpose         TEXT,
    qualified_name  TEXT,
    db_type         TEXT,
    physical_ref_json TEXT
);

-- Column-level mappings from tMap / extract_column_mappings()
CREATE TABLE IF NOT EXISTS mappings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    source_component    TEXT,
    source_column       TEXT,
    target_component    TEXT,
    target_column       TEXT,
    migration_rule      TEXT,
    expression          TEXT,
    data_type_conversion TEXT,
    default_value       TEXT
);

-- Index for fast look-ups by file path
CREATE INDEX IF NOT EXISTS idx_jobs_file_path ON jobs(file_path);
CREATE INDEX IF NOT EXISTS idx_components_job  ON components(job_id);
CREATE INDEX IF NOT EXISTS idx_sources_job     ON sources(job_id);
CREATE INDEX IF NOT EXISTS idx_targets_job     ON targets(job_id);
CREATE INDEX IF NOT EXISTS idx_mappings_job    ON mappings(job_id);
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: str) -> str:
    """Return hex SHA-256 of a file's contents (chunk-based, memory-safe)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_json_loads(text: Optional[str]) -> object:
    if not text:
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def _physical_ref_to_dict(ref) -> dict:
    """Serialise a PhysicalTableRef dataclass (or plain dict) to a dict."""
    if ref is None:
        return {}
    if isinstance(ref, dict):
        return ref
    # dataclass instance
    return {
        "unique_name":    getattr(ref, "unique_name",    ""),
        "component_type": getattr(ref, "component_type", ""),
        "db_type":        getattr(ref, "db_type",        ""),
        "database":       getattr(ref, "database",       ""),
        "schema":         getattr(ref, "schema",         ""),
        "table":          getattr(ref, "table",          ""),
        "file_name":      getattr(ref, "file_name",      ""),
        "query_snippet":  getattr(ref, "query_snippet",  ""),
        "is_file":        getattr(ref, "is_file",        False),
        "is_resolved":    getattr(ref, "is_resolved",    False),
        "qualified_name": getattr(ref, "qualified_name", ""),
        "physical_key":   getattr(ref, "physical_key",   ""),
    }


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class CacheManager:
    """
    SQLite-backed metadata cache for Talend Migration Accelerator.

    Parameters
    ----------
    db_path : str | Path
        Filesystem path to the SQLite database.  Created (with all
        parent directories) on first instantiation.
    """

    def __init__(self, db_path: str | Path = _DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._connect() as conn:
            conn.executescript(_DDL)
        logger.debug("Cache DB ready: %s", self.db_path)

    # ------------------------------------------------------------------
    # Cache-read helpers
    # ------------------------------------------------------------------

    def get_job(self, file_path: str) -> Optional[dict]:
        """
        Return the cached job_info dict for *file_path*, or None on miss.

        Does NOT check staleness — call is_stale() first if freshness matters.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT raw_json FROM jobs WHERE file_path = ?",
                (os.path.abspath(file_path),)
            ).fetchone()
        if row is None:
            return None
        return _safe_json_loads(row["raw_json"])

    def get_all_jobs(self) -> List[dict]:
        """Return every cached job_info dict (newest first)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT raw_json FROM jobs ORDER BY cached_at DESC"
            ).fetchall()
        return [_safe_json_loads(r["raw_json"]) for r in rows]

    def get_all_job_paths(self) -> List[str]:
        """Return all file paths currently in the cache."""
        with self._connect() as conn:
            rows = conn.execute("SELECT file_path FROM jobs").fetchall()
        return [r["file_path"] for r in rows]

    def get_components(self, file_path: str) -> List[dict]:
        """Return cached component rows for a specific job."""
        with self._connect() as conn:
            job_row = conn.execute(
                "SELECT id FROM jobs WHERE file_path = ?",
                (os.path.abspath(file_path),)
            ).fetchone()
            if job_row is None:
                return []
            rows = conn.execute(
                "SELECT unique_name, component_type, parameters_json "
                "FROM components WHERE job_id = ?",
                (job_row["id"],)
            ).fetchall()
        result = []
        for r in rows:
            comp = {
                "unique_name":    r["unique_name"],
                "component_type": r["component_type"],
                "parameters":     _safe_json_loads(r["parameters_json"]),
            }
            result.append(comp)
        return result

    def get_sources(self, file_path: str) -> List[dict]:
        """Return cached source rows for a specific job."""
        return self._get_io_rows("sources", file_path)

    def get_targets(self, file_path: str) -> List[dict]:
        """Return cached target rows for a specific job."""
        return self._get_io_rows("targets", file_path)

    def _get_io_rows(self, table: str, file_path: str) -> List[dict]:
        with self._connect() as conn:
            job_row = conn.execute(
                "SELECT id FROM jobs WHERE file_path = ?",
                (os.path.abspath(file_path),)
            ).fetchone()
            if job_row is None:
                return []
            rows = conn.execute(
                f"SELECT name, component_type, unique_name, purpose, "
                f"       qualified_name, db_type, physical_ref_json "
                f"FROM {table} WHERE job_id = ?",
                (job_row["id"],)
            ).fetchall()
        result = []
        for r in rows:
            result.append({
                "name":           r["name"],
                "component_type": r["component_type"],
                "unique_name":    r["unique_name"],
                "purpose":        r["purpose"],
                "qualified_name": r["qualified_name"],
                "db_type":        r["db_type"],
                "physical_ref":   _safe_json_loads(r["physical_ref_json"]),
            })
        return result

    def get_mappings(self, file_path: str) -> List[dict]:
        """Return cached column-mapping rows for a specific job."""
        with self._connect() as conn:
            job_row = conn.execute(
                "SELECT id FROM jobs WHERE file_path = ?",
                (os.path.abspath(file_path),)
            ).fetchone()
            if job_row is None:
                return []
            rows = conn.execute(
                "SELECT source_component, source_column, target_component, "
                "       target_column, migration_rule, expression, "
                "       data_type_conversion, default_value "
                "FROM mappings WHERE job_id = ?",
                (job_row["id"],)
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Cache-write helpers
    # ------------------------------------------------------------------

    def put_job(self, file_path: str, job_data: dict,
                sources: Optional[List[dict]] = None,
                targets: Optional[List[dict]] = None) -> None:
        """
        Persist a parsed job and its sub-entities.

        Parameters
        ----------
        file_path : str
            Absolute or relative path to the .item file.
        job_data  : dict
            Return value of TalendJobParser.extract_job_info().
        sources   : list[dict] | None
            Output of source_target_extractor.extract_sources().
        targets   : list[dict] | None
            Output of source_target_extractor.extract_targets().
        """
        abs_path = os.path.abspath(file_path)
        try:
            file_mtime = os.path.getmtime(abs_path)
            file_hash  = _sha256(abs_path)
        except OSError:
            file_mtime = 0.0
            file_hash  = ""

        with self._connect() as conn:
            # Upsert job row
            conn.execute("""
                INSERT INTO jobs
                    (file_path, file_hash, file_mtime, job_name, job_version,
                     talend_version, raw_json, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_hash      = excluded.file_hash,
                    file_mtime     = excluded.file_mtime,
                    job_name       = excluded.job_name,
                    job_version    = excluded.job_version,
                    talend_version = excluded.talend_version,
                    raw_json       = excluded.raw_json,
                    cached_at      = excluded.cached_at
            """, (
                abs_path,
                file_hash,
                file_mtime,
                job_data.get("job_name", ""),
                job_data.get("job_version", ""),
                job_data.get("talend_version", ""),
                json.dumps(job_data, default=str),
                time.time(),
            ))

            job_id = conn.execute(
                "SELECT id FROM jobs WHERE file_path = ?", (abs_path,)
            ).fetchone()["id"]

            # Clear old sub-entity rows (cascade would also do this, but
            # explicit deletes keep things predictable on upsert)
            for t in ("components", "sources", "targets", "mappings"):
                conn.execute(f"DELETE FROM {t} WHERE job_id = ?", (job_id,))

            # Persist components
            for comp in job_data.get("components", []):
                conn.execute("""
                    INSERT INTO components
                        (job_id, unique_name, component_type, parameters_json)
                    VALUES (?, ?, ?, ?)
                """, (
                    job_id,
                    comp.get("unique_name", ""),
                    comp.get("component_type", ""),
                    json.dumps(comp.get("parameters", {}), default=str),
                ))

            # Persist sources
            for src in (sources or []):
                conn.execute("""
                    INSERT INTO sources
                        (job_id, name, component_type, unique_name, purpose,
                         qualified_name, db_type, physical_ref_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    src.get("name", ""),
                    src.get("component_type", src.get("type", "")),
                    src.get("unique_name", src.get("component", "")),
                    src.get("purpose", ""),
                    src.get("qualified_name", ""),
                    src.get("db_type", ""),
                    json.dumps(_physical_ref_to_dict(src.get("physical_ref")), default=str),
                ))

            # Persist targets
            for tgt in (targets or []):
                conn.execute("""
                    INSERT INTO targets
                        (job_id, name, component_type, unique_name, purpose,
                         qualified_name, db_type, physical_ref_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    tgt.get("name", ""),
                    tgt.get("component_type", tgt.get("type", "")),
                    tgt.get("unique_name", tgt.get("component", "")),
                    tgt.get("purpose", ""),
                    tgt.get("qualified_name", ""),
                    tgt.get("db_type", ""),
                    json.dumps(_physical_ref_to_dict(tgt.get("physical_ref")), default=str),
                ))

            # Persist column mappings
            for m in job_data.get("column_mappings", []):
                conn.execute("""
                    INSERT INTO mappings
                        (job_id, source_component, source_column,
                         target_component, target_column, migration_rule,
                         expression, data_type_conversion, default_value)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    m.get("Source Component", ""),
                    m.get("Source Column", ""),
                    m.get("Target Component", ""),
                    m.get("Target Column", ""),
                    m.get("Migration Rule", ""),
                    m.get("Expression", ""),
                    m.get("Data Type Conversion", ""),
                    m.get("Default Value", ""),
                ))

        logger.debug("Cached job: %s (id=%s)", abs_path, job_id)

    # ------------------------------------------------------------------
    # Staleness / invalidation
    # ------------------------------------------------------------------

    def is_stale(self, file_path: str) -> bool:
        """
        Return True if the file has changed on disk since it was cached,
        or if it is not cached at all.
        """
        abs_path = os.path.abspath(file_path)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT file_mtime FROM jobs WHERE file_path = ?",
                (abs_path,)
            ).fetchone()
        if row is None:
            return True                         # not in cache → stale
        try:
            current_mtime = os.path.getmtime(abs_path)
        except OSError:
            return True                         # file gone → stale
        return abs(current_mtime - row["file_mtime"]) > 1e-3

    def invalidate(self, file_path: str) -> None:
        """Remove one job (and its sub-entities via CASCADE) from the cache."""
        abs_path = os.path.abspath(file_path)
        with self._connect() as conn:
            conn.execute("DELETE FROM jobs WHERE file_path = ?", (abs_path,))
        logger.info("Cache invalidated: %s", abs_path)

    def clear(self) -> None:
        """Wipe the entire cache (all tables)."""
        with self._connect() as conn:
            for t in ("mappings", "targets", "sources", "components", "jobs"):
                conn.execute(f"DELETE FROM {t}")
        logger.info("Cache cleared: %s", self.db_path)

    # ------------------------------------------------------------------
    # High-level load_or_parse
    # ------------------------------------------------------------------

    def load_or_parse(
        self,
        file_path: str,
        force_refresh: bool = False,
    ) -> dict:
        """
        Return job metadata from cache when fresh, parsing the XML only when
        the cache is empty, stale, or *force_refresh* is True.

        This is the recommended entry-point for all consumers that currently
        instantiate TalendJobParser directly.

        Parameters
        ----------
        file_path     : str   Path to the .item file.
        force_refresh : bool  Skip staleness check and re-parse unconditionally.

        Returns
        -------
        dict  As returned by TalendJobParser.extract_job_info().
        """
        abs_path = os.path.abspath(file_path)

        if not force_refresh and not self.is_stale(abs_path):
            cached = self.get_job(abs_path)
            if cached is not None:
                logger.debug("Cache HIT: %s", abs_path)
                return cached

        # Cache miss or stale — parse the XML
        logger.debug("Cache MISS (parsing): %s", abs_path)
        from app.parser.talend_xml_parser import TalendJobParser  # local import to avoid cycles

        parser   = TalendJobParser(abs_path)
        job_data = parser.extract_job_info()

        # Attempt to extract source/target inventory (best-effort)
        sources: List[dict] = []
        targets: List[dict] = []
        try:
            from app.parser.source_target_extractor import (
                extract_sources,
                extract_targets,
            )
            components = job_data.get("components", [])
            sources    = extract_sources(components)
            targets    = extract_targets(components)
        except Exception as exc:
            logger.warning("source_target_extractor failed for %s: %s", abs_path, exc)

        self.put_job(abs_path, job_data, sources=sources, targets=targets)
        return job_data

    def load_or_parse_many(
        self,
        file_paths: List[str],
        force_refresh: bool = False,
        progress_callback=None,
    ) -> List[dict]:
        """
        Bulk variant of load_or_parse.  Processes each file and returns a list
        of job_info dicts in the same order as *file_paths*.

        Parameters
        ----------
        file_paths        : list[str]
        force_refresh     : bool
        progress_callback : callable(current, total) | None
            Called after each file is processed.
        """
        results = []
        total = len(file_paths)
        for idx, fp in enumerate(file_paths):
            try:
                results.append(self.load_or_parse(fp, force_refresh=force_refresh))
            except Exception as exc:
                logger.error("Failed to parse %s: %s", fp, exc)
            if progress_callback:
                try:
                    progress_callback(idx + 1, total)
                except Exception:
                    pass
        return results

    # ------------------------------------------------------------------
    # Introspection / stats
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """Return row-count summary for every cache table."""
        with self._connect() as conn:
            counts = {}
            for t in ("jobs", "components", "sources", "targets", "mappings"):
                row = conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()
                counts[t] = row["n"]
        return counts

    def job_summary(self) -> List[dict]:
        """
        Return a lightweight summary list (no raw_json) for all cached jobs.
        Useful for building UI dashboards without deserialising every blob.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT file_path, job_name, job_version, talend_version, "
                "       file_mtime, cached_at "
                "FROM jobs ORDER BY job_name"
            ).fetchall()
        return [dict(r) for r in rows]

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"CacheManager(db={self.db_path!r}, "
            f"jobs={s['jobs']}, components={s['components']}, "
            f"sources={s['sources']}, targets={s['targets']}, "
            f"mappings={s['mappings']})"
        )
