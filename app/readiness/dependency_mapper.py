"""
ReadinessDependencyMapper  (F2.1)

Scans the codebase for import relationships among the readiness-related
modules and builds a dependency map: for each readiness module, which other
readiness modules it imports, and which modules (readiness or not) import it.
"""

import ast
import os
from typing import Dict, List, Set

READINESS_MODULES: List[str] = [
    "app.readiness.component_compatibility",
    "app.tiap.assessment.cloud_readiness",
    "app.analyzers.readiness_scorer",
    "app.analyzers.cloud_readiness",
    "app.analyzers.migration_readiness_score",
]


def _module_name_for_path(path: str, root: str) -> str:
    rel = os.path.relpath(path, root)
    rel = rel[:-3] if rel.endswith(".py") else rel
    return rel.replace(os.sep, ".")


def _extract_imports(path: str) -> Set[str]:
    imports: Set[str] = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (SyntaxError, OSError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports


def build_dependency_map(project_root: str = ".") -> Dict[str, Dict[str, List[str]]]:
    """Returns {readiness_module: {"imports": [...], "imported_by": [...]}}."""
    app_root = os.path.join(project_root, "app")
    file_imports: Dict[str, Set[str]] = {}

    for root, _dirs, files in os.walk(app_root):
        if "temp_repository" in root or "__pycache__" in root:
            continue
        for fname in files:
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                mod_name = _module_name_for_path(fpath, project_root)
                file_imports[mod_name] = _extract_imports(fpath)

    result: Dict[str, Dict[str, List[str]]] = {}
    for readiness_mod in READINESS_MODULES:
        imports = sorted(
            i for i in file_imports.get(readiness_mod, set()) if i in READINESS_MODULES
        )
        imported_by = sorted(
            mod for mod, imps in file_imports.items()
            if mod != readiness_mod and readiness_mod in imps
        )
        result[readiness_mod] = {"imports": imports, "imported_by": imported_by}

    return result


def find_orphan_modules(dependency_map: Dict[str, Dict[str, List[str]]]) -> List[str]:
    """Readiness modules with no internal/external dependents (dead-code candidates)."""
    return sorted(mod for mod, edges in dependency_map.items() if not edges["imported_by"])
