#!/usr/bin/env python3
"""
F8.9 — Pre-release validation script.
Scans the repository for forbidden development artifacts before packaging.
Exits non-zero (fails the build) if any are found.

Usage: python3 scripts/validate_release.py [repo_root]
"""
from __future__ import annotations
import fnmatch
import os
import sys

# Directory name patterns — any directory matching these is forbidden anywhere
# in the tree (matched against the directory's basename).
FORBIDDEN_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".ipynb_checkpoints", "htmlcov", "temp_repository", "pre_migration_temp",
}
FORBIDDEN_DIR_SUFFIXES = (".egg-info",)

# File name glob patterns — forbidden anywhere in the tree.
FORBIDDEN_FILE_GLOBS = (
    "*.pyc", "*.pyo", "*.pyd",
    ".aider*",
    ".DS_Store", "Thumbs.db", "*.swp",
    ".coverage",
)

# Exact root-relative paths that are forbidden (generated run output).
FORBIDDEN_ROOT_PATHS = {
    "output", "migration_report.xlsx", "pre_migration_repo.zip",
}

# Paths excluded from the scan itself (this script's own cache, vcs metadata).
SKIP_DIR_NAMES = {".git"}


def scan(repo_root: str) -> list[str]:
    violations: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]

        rel_dir = os.path.relpath(dirpath, repo_root)
        for d in list(dirnames):
            full = os.path.join(dirpath, d)
            if d in FORBIDDEN_DIR_NAMES or d.endswith(FORBIDDEN_DIR_SUFFIXES):
                violations.append(os.path.relpath(full, repo_root) + "/")

        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, repo_root)
            if any(fnmatch.fnmatch(f, pat) for pat in FORBIDDEN_FILE_GLOBS):
                violations.append(rel)

    for p in FORBIDDEN_ROOT_PATHS:
        full = os.path.join(repo_root, p)
        if os.path.exists(full):
            rel = p + ("/" if os.path.isdir(full) else "")
            if rel not in violations:
                violations.append(rel)

    return sorted(set(violations))


def main() -> int:
    repo_root = sys.argv[1] if len(sys.argv) > 1 else "."
    repo_root = os.path.abspath(repo_root)

    if not os.path.isdir(repo_root):
        print(f"ERROR: repo root not found: {repo_root}")
        return 2

    violations = scan(repo_root)

    if violations:
        print(f"RELEASE VALIDATION: FAILED ({len(violations)} forbidden artifact(s) found)")
        for v in violations:
            print(f"  - {v}")
        print("\nRemove these before packaging, or run the F8.7 cleanup step.")
        return 1

    print("RELEASE VALIDATION: PASSED — no forbidden development artifacts found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
