#!/usr/bin/env python3
"""
build_phase1c_lineage_cache.py
================================
Rebuilds ``cache/phase_1c/lineage_cache.json`` from the actual Talend
``.item`` job files in ``temp_repository/``.

The original (broken) cache was built by scanning the TMA Python source tree,
so every key in ``job_lineage`` was a Python module path like
``app/cloud_integration/talend_cloud_client.py``.  This script replaces it
with a cache whose keys are **Talend job names** (e.g. ``SC_AS400_To_DropZone_MD``),
matching what ``job_data["job_name"]`` returns in the Job 360 UI.

Usage (run from the TMA project root):
    python build_phase1c_lineage_cache.py
    python build_phase1c_lineage_cache.py path/to/your/talend_repo
    python build_phase1c_lineage_cache.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from typing import Any

# ── make sure the project root is on sys.path ─────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUTPUT_PATH = os.path.join(ROOT, "cache", "phase_1c", "lineage_cache.json")
DEFAULT_REPO = os.path.join(ROOT, "temp_repository")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — lightweight versions that avoid importing the full Streamlit stack
# ─────────────────────────────────────────────────────────────────────────────

def _find_item_files(repo_path: str) -> list[str]:
    """Walk *repo_path* and return every .item file inside a 'process' folder."""
    found: list[str] = []
    for root, _dirs, files in os.walk(repo_path):
        if "process" not in root.lower():
            continue
        for fname in files:
            if fname.endswith(".item"):
                found.append(os.path.join(root, fname))
    return sorted(found)


def _job_name_from_path(item_path: str) -> str:
    """Derive Talend job name from file path (strips version suffix _X.Y)."""
    base = os.path.basename(item_path).replace(".item", "")
    return re.sub(r"_\d+\.\d+$", "", base)


def _parse_item(item_path: str) -> dict:
    """Parse a Talend .item XML file and return a minimal job_data dict.

    Falls back gracefully if the full TalendJobParser is unavailable.
    """
    job_name = _job_name_from_path(item_path)
    try:
        from app.parser.talend_xml_parser import TalendJobParser
        parser = TalendJobParser(item_path)
        if not parser.is_valid_job():
            log.warning("  SKIP  %s — not a valid Talend job", item_path)
            return {}
        data = parser.extract_job_info()
        return data
    except Exception as exc:  # pragma: no cover
        log.warning("  PARSE FAIL  %s — %s; using minimal stub", item_path, exc)
        return {"job_name": job_name, "components": [], "column_mappings": [], "mapping_rules": []}


def _complexity(job_data: dict) -> dict:
    """Return {score, level, risk_factors} for *job_data*."""
    try:
        from app.analyzers.complexity_analyzer import calculate_complexity
        result = calculate_complexity(job_data)
        return {
            "complexity_score": result.get("score", 0),
            "complexity_level": result.get("complexity_band", result.get("complexity", "LOW")),
            "risk_factors": result.get("risk_factors", []),
        }
    except Exception:
        return {"complexity_score": 0, "complexity_level": "LOW", "risk_factors": []}


def _component_counts(job_data: dict) -> dict:
    """Count component types that feed into the lineage record."""
    tmap = db = java = total = 0
    java_names: list[str] = []
    for comp in job_data.get("components", []):
        ctype = comp.get("component_type", "") if isinstance(comp, dict) else str(comp)
        total += 1
        if "tmap" in ctype.lower():
            tmap += 1
        if any(x in ctype.lower() for x in ("jdbc", "mysql", "oracle", "mssql", "postgres", "db", "sql")):
            db += 1
        if ctype.lower() in ("tjava", "tjavaflex", "tjavainput", "tjavarow", "tjavainput"):
            java += 1
            name = comp.get("unique_name", ctype) if isinstance(comp, dict) else ctype
            java_names.append(name)
    return {
        "component_count": total,
        "tmap_count": tmap,
        "db_component_count": db,
        "custom_java_count": java,
        "java_components": java_names,
    }


def _sql_operations(job_data: dict) -> list[dict]:
    """Extract SQL operation stubs from mapping_rules / column_mappings."""
    ops: list[dict] = []
    for mr in job_data.get("mapping_rules", []):
        stmt = mr.get("expression") or mr.get("sql") or ""
        table = mr.get("target_table") or mr.get("source_table") or ""
        if stmt and re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\b", stmt, re.I):
            ops.append({"statement": stmt, "table_name": table})
    return ops


def _child_jobs(job_data: dict) -> list[str]:
    """Return list of child/called job names from components."""
    children: list[str] = []
    for comp in job_data.get("components", []):
        if not isinstance(comp, dict):
            continue
        ctype = comp.get("component_type", "")
        if ctype.lower() in ("trunJob", "tchild", "tpreJobtask", "tpostjobtask",
                              "trunjob", "tchilTask"):
            child = (comp.get("parameters", {}) or {}).get("PROCESS_TYPE_PROCESS") \
                or comp.get("unique_name", "")
            if child:
                children.append(child)
    return children


# ─────────────────────────────────────────────────────────────────────────────
# Table lineage (derived from column mappings)
# ─────────────────────────────────────────────────────────────────────────────

def _build_table_lineage(all_jobs: list[dict]) -> dict[str, dict]:
    """
    Build table_lineage keyed by table name, aggregating read/write records
    across all jobs — mirroring the schema used by cached_lineage_page.py.
    """
    tables: dict[str, dict] = {}

    for jd in all_jobs:
        job_name = jd.get("job_name", "")
        for mapping in jd.get("column_mappings", []):
            src_table = mapping.get("source_table", "")
            tgt_table = mapping.get("target_table", "")

            if src_table:
                entry = tables.setdefault(src_table, {
                    "table_name": src_table, "reads": [], "writes": [], "ddl": [], "modules": []
                })
                entry["reads"].append({"module": job_name, "statement": ""})
                if job_name not in entry["modules"]:
                    entry["modules"].append(job_name)

            if tgt_table:
                entry = tables.setdefault(tgt_table, {
                    "table_name": tgt_table, "reads": [], "writes": [], "ddl": [], "modules": []
                })
                entry["writes"].append({"module": job_name, "statement": ""})
                if job_name not in entry["modules"]:
                    entry["modules"].append(job_name)

    return tables


# ─────────────────────────────────────────────────────────────────────────────
# Dependency graph (job → child jobs)
# ─────────────────────────────────────────────────────────────────────────────

def _build_dependency_graph(all_jobs: list[dict]) -> dict[str, dict]:
    """
    Build dependency_graph keyed by job_name.

    ``imports``     — child jobs this job calls (tRunJob etc.)
    ``imported_by`` — parent jobs that call this job
    """
    children_map: dict[str, list[str]] = {}
    all_names: set[str] = set()

    for jd in all_jobs:
        name = jd.get("job_name", "")
        all_names.add(name)
        children_map[name] = _child_jobs(jd)

    # Build reverse index
    parents_map: dict[str, list[str]] = defaultdict(list)
    for parent, children in children_map.items():
        for child in children:
            parents_map[child].append(parent)

    dep: dict[str, dict] = {}
    for jd in all_jobs:
        name = jd.get("job_name", "")
        # Derive a "package" from the relative path of the .item file
        # so the UI can group jobs (e.g. "SupplyChain_Phase6_1")
        file_path = jd.get("_item_path", "")
        package = os.path.basename(os.path.dirname(file_path)) if file_path else ""
        dep[name] = {
            "module": name,
            "package": package,
            "imports": sorted(set(children_map.get(name, []))),
            "imported_by": sorted(set(parents_map.get(name, []))),
        }

    return dep


# ─────────────────────────────────────────────────────────────────────────────
# Column lineage metadata (engine capabilities — does not change per job)
# ─────────────────────────────────────────────────────────────────────────────

_COLUMN_LINEAGE_META: dict[str, Any] = {
    "node_types": ["SOURCE_TABLE", "TARGET_TABLE", "COMPONENT", "LOOKUP_TABLE"],
    "edge_types": ["DATA_FLOW", "JOIN", "LOOKUP"],
    "transformation_types": ["mapping", "expression", "aggregation", "join", "lookup", "filter"],
    "cross_job_bridging": True,
    "physical_resolution": True,
    "column_level_fields": {
        "source": ["source_table", "source_column", "source_component"],
        "target": ["target_table", "target_column", "target_component"],
        "transform": ["expression", "rule_type", "tmap_component"],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Migration scores — aggregate from complexity
# ─────────────────────────────────────────────────────────────────────────────

def _migration_scores(job_lineage: dict[str, dict]) -> dict:
    scores = [r.get("complexity_score", 0) for r in job_lineage.values()]
    levels = [r.get("complexity_level", "LOW") for r in job_lineage.values()]
    avg = round(sum(scores) / len(scores), 1) if scores else 0
    level_counts = {lv: levels.count(lv) for lv in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}

    # Readiness: inverse of average complexity (capped 0-100)
    readiness = max(0, min(100, int(100 - avg)))

    return {
        "average_complexity_score": avg,
        "complexity_distribution": level_counts,
        "migration_readiness": readiness,
        "migration_rag": "GREEN" if readiness >= 70 else "AMBER" if readiness >= 40 else "RED",
        "migration_status": "READY" if readiness >= 70 else "REVIEW" if readiness >= 40 else "BLOCKED",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main build
# ─────────────────────────────────────────────────────────────────────────────

def build_cache(repo_path: str, dry_run: bool = False) -> dict:
    t0 = time.perf_counter()
    log.info("Scanning for Talend .item files in: %s", repo_path)

    item_files = _find_item_files(repo_path)
    if not item_files:
        log.error("No .item files found under %s/process/. "
                  "Check that the repo path is correct.", repo_path)
        sys.exit(1)

    log.info("Found %d .item file(s). Parsing…", len(item_files))

    all_jobs: list[dict] = []
    job_lineage: dict[str, dict] = {}
    skipped = 0

    for i, item_path in enumerate(item_files, 1):
        jd = _parse_item(item_path)
        if not jd:
            skipped += 1
            continue

        jd["_item_path"] = item_path          # internal bookkeeping, stripped later
        job_name: str = jd.get("job_name", "")
        if not job_name or job_name == "INVALID_JOB":
            log.warning("  SKIP  %s — no job_name resolved", item_path)
            skipped += 1
            continue

        comps = _component_counts(jd)
        cx = _complexity(jd)
        sql_ops = _sql_operations(jd)

        # Derive package from the folder name one level above process/
        rel = os.path.relpath(item_path, repo_path)
        parts = rel.replace("\\", "/").split("/")
        # typical: SUPPLYCHAIN_MDM/process/SupplyChain_Phase6_1/SC_AS400_To_DropZone_MD_3.1.item
        package = parts[2] if len(parts) >= 4 else (parts[0] if parts else "")

        job_lineage[job_name] = {
            "module": job_name,                              # key == module for compatibility
            "package": package,
            "module_name": job_name,                        # explicit match field used by _default_module
            "job_version": jd.get("job_version", ""),
            "talend_version": jd.get("talend_version", ""),
            "lines": 0,                                      # N/A for .item files
            "classes": 0,
            "functions": 0,
            "internal_imports": [],
            "called_jobs": _child_jobs(jd),
            **cx,
            **comps,
            "sql_operations": sql_ops,
        }

        all_jobs.append(jd)
        log.info("  [%d/%d]  %-50s  %s  score=%s",
                 i, len(item_files), job_name,
                 cx["complexity_level"], cx["complexity_score"])

    log.info("Parsed %d job(s), skipped %d.", len(all_jobs), skipped)

    # Strip internal bookkeeping field before further use
    for jd in all_jobs:
        jd.pop("_item_path", None)

    log.info("Building table lineage…")
    table_lineage = _build_table_lineage(all_jobs)
    log.info("  → %d unique table(s) found", len(table_lineage))

    log.info("Building dependency graph…")
    dependency_graph = _build_dependency_graph(all_jobs)

    ms = _migration_scores(job_lineage)
    total_components = sum(r["component_count"] for r in job_lineage.values())

    cache: dict = {
        "metadata": {
            "version": "1C",
            "phase": "Phase_1C",
            "source_phase": "Talend .item parse (build_phase1c_lineage_cache.py)",
            "total_modules": len(job_lineage),
            "total_jobs": len(job_lineage),
            "total_components": total_components,
            "migration_readiness": ms["migration_readiness"],
            "migration_rag": ms["migration_rag"],
            "migration_status": ms["migration_status"],
            "repo_path": repo_path,
            "built_from": "talend_item_files",   # distinct from the broken "python_source" origin
        },
        "migration_scores": ms,
        "repository_summary": {
            "total_jobs": len(job_lineage),
            "total_tables": len(table_lineage),
            "complexity_distribution": ms["complexity_distribution"],
        },
        "job_lineage": job_lineage,
        "table_lineage": table_lineage,
        "column_lineage": _COLUMN_LINEAGE_META,
        "dependency_graph": dependency_graph,
    }

    elapsed = time.perf_counter() - t0
    log.info("Cache built in %.1f s — %d jobs, %d tables, %d dependency entries.",
             elapsed, len(job_lineage), len(table_lineage), len(dependency_graph))

    if dry_run:
        log.info("DRY RUN — not writing to disk. Would write to: %s", OUTPUT_PATH)
        print(json.dumps({k: v for k, v in cache.items() if k != "job_lineage"}, indent=2))
        print(f"  … and {len(job_lineage)} job_lineage entries (omitted for brevity)")
    else:
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        log.info("Written to: %s", OUTPUT_PATH)

    return cache


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers — useful to call after a rebuild
# ─────────────────────────────────────────────────────────────────────────────

def validate_cache(cache_path: str = OUTPUT_PATH) -> bool:
    """Quick sanity check: ensure keys look like Talend job names, not .py paths."""
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("job_lineage", {})
    if not jobs:
        log.error("FAIL: job_lineage is empty")
        return False

    python_keys = [k for k in jobs if k.endswith(".py") or k.startswith("app/")]
    if python_keys:
        log.error("FAIL: %d job_lineage keys look like Python paths: %s …",
                  len(python_keys), python_keys[:3])
        return False

    log.info("PASS: %d job_lineage entries, keys look like Talend job names.", len(jobs))
    log.info("Sample keys: %s", list(jobs.keys())[:5])

    meta = data.get("metadata", {})
    log.info("Readiness: %s/100 (%s)", meta.get("migration_readiness"), meta.get("migration_rag"))
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild cache/phase_1c/lineage_cache.json from Talend .item files."
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=DEFAULT_REPO,
        help=f"Path to Talend repository root (default: {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and print summary without writing the cache file",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate an existing cache file without rebuilding",
    )
    args = parser.parse_args()

    if args.validate_only:
        ok = validate_cache()
        sys.exit(0 if ok else 1)

    if not os.path.isdir(args.repo_path):
        log.error("Repo path does not exist or is not a directory: %s", args.repo_path)
        sys.exit(1)

    cache = build_cache(args.repo_path, dry_run=args.dry_run)

    if not args.dry_run:
        log.info("Running validation…")
        validate_cache()


if __name__ == "__main__":
    main()
