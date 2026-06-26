"""Architecture anti-pattern detection for Talend repositories."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List

from app.migration_intelligence.dependency_graph import DependencyGraphEngine


PATH_RE = re.compile(r"([A-Za-z]:\\|/opt/|/var/|/tmp/|/home/|\\\\[^\\s]+)")
CRED_RE = re.compile(r"(password|passwd|pwd|secret|token|apikey|api_key)", re.I)
JAVA_TYPES = {"tJava", "tJavaRow", "tJavaFlex", "tJavaInput", "tJavaOutput", "tBeanShell", "tGroovy"}
ERROR_TYPES = {"tLogCatcher", "tDie", "tWarn", "tAssertCatcher", "tStatCatcher"}


def job_data(job: Dict[str, Any]) -> Dict[str, Any]:
    return job.get("job_data", job) if isinstance(job, dict) else {}


def components(job: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for c in (job_data(job).get("components", []) or []) if isinstance(c, dict)]


def ctype(component: Dict[str, Any]) -> str:
    return component.get("component_type") or component.get("type") or component.get("name") or ""


def params(component: Dict[str, Any]) -> Dict[str, Any]:
    raw = component.get("parameters", component.get("element_parameters", {})) or {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {str(x.get("name", i)): x.get("value", "") for i, x in enumerate(raw) if isinstance(x, dict)}
    return {}


def _text_values(component: Dict[str, Any]) -> Iterable[str]:
    for k, v in params(component).items():
        yield str(k)
        yield str(v)


def _severity(kind: str, count: int) -> str:
    if kind in {"hardcoded_credentials", "missing_error_handling", "deep_dependency_chains"} and count:
        return "HIGH"
    if count >= 5:
        return "HIGH"
    if count >= 2:
        return "MEDIUM"
    return "LOW"


class ArchitectureAntiPatternDetector:
    def detect(self, jobs, dependency_graph=None) -> Dict[str, Any]:
        jobs = list(jobs or [])
        findings: List[Dict[str, Any]] = []
        context_seen = defaultdict(set)
        signatures = defaultdict(list)

        for job in jobs:
            data = job_data(job)
            name = data.get("job_name", "Unknown")
            comps = components(job)
            types = [ctype(c) for c in comps]
            signatures[tuple(sorted(Counter(types).items()))].append(name)

            for ctx in (job.get("dependencies", {}) or {}).get("contexts", data.get("contexts", []) or []):
                key = ctx.get("name", str(ctx)) if isinstance(ctx, dict) else str(ctx)
                context_seen[key].add(name)

            if comps and not any(t in ERROR_TYPES for t in types):
                findings.append(self._finding("missing_error_handling", name, "Job has no catcher/die/warn error path.", 8))

            java_count = sum(t in JAVA_TYPES for t in types)
            if java_count > 2:
                findings.append(self._finding("excessive_inline_java", name, f"{java_count} inline Java/script components.", java_count))

            tmap_count = 0
            for comp in comps:
                values = list(_text_values(comp))
                text = " ".join(values)
                if any(PATH_RE.search(v) for v in values):
                    findings.append(self._finding("hardcoded_paths", name, f"Hardcoded path in {ctype(comp)}.", 5, ctype(comp)))
                if any(CRED_RE.search(k) and str(v).strip().strip('"\'') for k, v in params(comp).items()):
                    findings.append(self._finding("hardcoded_credentials", name, f"Credential-like literal in {ctype(comp)}.", 10, ctype(comp)))
                if ctype(comp) in {"tMap", "tXMLMap", "tELTMap"}:
                    tmap_count += 1
                    if len(text) > 1500 or text.count("expression") > 20 or text.count(";") > 30:
                        findings.append(self._finding("excessive_tmap_complexity", name, "Large mapping/expression payload.", 7, ctype(comp)))
            if tmap_count > 4:
                findings.append(self._finding("excessive_tmap_complexity", name, f"{tmap_count} map components in one job.", tmap_count))

        for ctx, users in context_seen.items():
            if len(users) > 3:
                findings.append(self._finding("context_duplication", ", ".join(sorted(users)), f"Context '{ctx}' duplicated across {len(users)} jobs.", len(users)))

        for sig, names in signatures.items():
            if len(sig) and len(names) > 1:
                findings.append(self._finding("duplicate_job_logic", ", ".join(sorted(names)), f"{len(names)} jobs share the same component signature.", len(names)))

        graph = dependency_graph or DependencyGraphEngine().build(jobs)
        depth = self._max_depth(graph.get("adjacency", {}))
        if depth > 4:
            findings.append(self._finding("deep_dependency_chains", "repository", f"Maximum job dependency depth is {depth}.", depth * 2))

        summary = Counter(f["type"] for f in findings)
        return {
            "findings": findings,
            "summary": dict(summary),
            "total": len(findings),
            "risk_score": min(100, sum(f["risk_points"] for f in findings)),
        }

    @staticmethod
    def _finding(kind, asset, message, points, component=None):
        return {"type": kind, "asset": asset, "component": component, "message": message,
                "severity": _severity(kind, points), "risk_points": int(points)}

    @staticmethod
    def _max_depth(adjacency):
        def dfs(node, seen):
            if node in seen:
                return 0
            children = adjacency.get(node, []) or []
            return 1 + max([dfs(c, seen | {node}) for c in children] or [0])
        return max([dfs(n, set()) for n in adjacency] or [0])



