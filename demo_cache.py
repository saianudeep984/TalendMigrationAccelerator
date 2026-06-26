#!/usr/bin/env python3
"""
demo_cache.py
=============
Quick demonstration and smoke-test for the TMA SQLite cache.

Run from the project root:
    python demo_cache.py [path/to/repo_or_item_file]

With no argument, uses the bundled sample project.
"""

import os
import sys
import time

# ── make sure the project root is on sys.path ─────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.cache.cache_manager import CacheManager
from app.parser.repository_scanner import find_talend_jobs


def hr(title=""):
    line = "─" * 60
    print(f"\n{line}")
    if title:
        print(f"  {title}")
        print(line)


def main():
    # ── resolve repo / item path ──────────────────────────────────────────
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = os.path.join(ROOT, "sample_projects")

    if os.path.isfile(target) and target.endswith(".item"):
        job_files = [target]
    elif os.path.isdir(target):
        job_files = find_talend_jobs(target)
    else:
        print(f"ERROR: cannot read {target!r}")
        sys.exit(1)

    print(f"\nTMA SQLite Cache Demo")
    print(f"  Repo  : {target}")
    print(f"  Jobs  : {len(job_files)} .item file(s) found")

    # ── open cache (stored next to this script) ───────────────────────────
    db_path = os.path.join(ROOT, "cache", "tma_cache.db")
    cm = CacheManager(db_path)
    cm.clear()   # start fresh for the demo

    hr("FIRST PASS  (cache MISS → XML parse)")
    t0 = time.perf_counter()
    for fp in job_files:
        job = cm.load_or_parse(fp)
        print(f"  [MISS] {job.get('job_name', '?')} "
              f"({len(job.get('components', []))} components, "
              f"{len(job.get('column_mappings', []))} mappings)")
    elapsed_miss = time.perf_counter() - t0
    print(f"\n  ⏱  {elapsed_miss*1000:.1f} ms total")

    hr("SECOND PASS  (cache HIT → SQLite)")
    t0 = time.perf_counter()
    for fp in job_files:
        job = cm.load_or_parse(fp)
        print(f"  [HIT]  {job.get('job_name', '?')}")
    elapsed_hit = time.perf_counter() - t0
    print(f"\n  ⏱  {elapsed_hit*1000:.1f} ms total")

    if elapsed_miss > 0:
        print(f"  🚀  Speed-up: {elapsed_miss / max(elapsed_hit, 0.001):.1f}×")

    hr("Cache Statistics")
    stats = cm.stats()
    for table, count in stats.items():
        print(f"  {table:<12} {count:>6} rows")

    hr("Job Summary (from cache, no XML touched)")
    for row in cm.job_summary():
        print(f"  {row['job_name']:<40} v{row['job_version'] or '?'}  "
              f"(Talend {row['talend_version'] or '?'})")

    hr("Staleness Check")
    for fp in job_files:
        stale = cm.is_stale(fp)
        print(f"  {'STALE' if stale else 'fresh':<6}  {os.path.basename(fp)}")

    hr("Selective Invalidation")
    if job_files:
        fp = job_files[0]
        name = os.path.basename(fp)
        print(f"  Invalidating: {name}")
        cm.invalidate(fp)
        stale = cm.is_stale(fp)
        print(f"  is_stale() after invalidate → {stale}  (expected: True)")

    hr("Cache repr()")
    print(f"  {cm!r}")

    print("\n✅  Demo complete.\n")


if __name__ == "__main__":
    main()
