import json
import logging
import os
from typing import Any, Dict, List, Sequence

from app.analyzers.routine_analyzer import analyze_routines
from app.analyzers.joblet_analyzer import analyze_joblets
from app.analyzers.dependency_analyzer import analyze_dependencies
from app.parser.source_target_extractor import extract_sources, extract_targets

logger = logging.getLogger(__name__)


class KnowledgeHubBuilder:

    def __init__(self, all_jobs: Sequence[Dict[str, Any]], output_dir: str = "output"):
        self.all_jobs = all_jobs
        self.output_dir = output_dir

    def build(self) -> str:
        knowledge = {
            "business_glossary":   self._business_glossary(),
            "source_systems":      self._source_systems(),
            "target_systems":      self._target_systems(),
            "component_catalog":   self._component_catalog(),
            "routine_catalog":     self._routine_catalog(),
            "joblet_catalog":      self._joblet_catalog(),
            "dependency_catalog":  self._dependency_catalog(),
            "migration_playbook":  self._migration_playbook(),
            "duplicate_artifacts": self._duplicate_artifacts(),
        }
        path = os.path.join(self.output_dir, "repository_knowledge.json")
        os.makedirs(self.output_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(knowledge, f, indent=2)
        return path

    def _business_glossary(self) -> List[dict]:
        terms = []
        seen = set()
        for job in self.all_jobs:
            jd = job.get("job_data", job)
            name = jd.get("job_name", "")
            desc = jd.get("description", jd.get("label", ""))
            if name and name not in seen:
                seen.add(name)
                terms.append({"term": name, "definition": desc or f"Talend job: {name}", "source_job": name})
        return terms

    def _source_systems(self) -> List[dict]:
        sources = {}
        try:
            for job in self.all_jobs:
                jd = job.get("job_data", job)
                job_name = jd.get("job_name", "unknown")
                for item in extract_sources(jd.get("components", [])):
                    key = item.get("connection", item.get("table", "unknown"))
                    if key not in sources:
                        sources[key] = {"name": key, "type": item.get("db_type", item.get("type", "unknown")),
                                        "connection": item.get("connection", ""), "jobs_using": []}
                    if job_name not in sources[key]["jobs_using"]:
                        sources[key]["jobs_using"].append(job_name)
        except Exception:
            logger.exception("Failed to build source systems knowledge.")
            pass
        return list(sources.values())

    def _target_systems(self) -> List[dict]:
        targets = {}
        try:
            for job in self.all_jobs:
                jd = job.get("job_data", job)
                job_name = jd.get("job_name", "unknown")
                for item in extract_targets(jd.get("components", [])):
                    key = item.get("connection", item.get("table", "unknown"))
                    if key not in targets:
                        targets[key] = {"name": key, "type": item.get("db_type", item.get("type", "unknown")),
                                        "connection": item.get("connection", ""), "jobs_using": []}
                    if job_name not in targets[key]["jobs_using"]:
                        targets[key]["jobs_using"].append(job_name)
        except Exception:
            logger.exception("Failed to build target systems knowledge.")
            pass
        return list(targets.values())

    def _component_catalog(self) -> List[dict]:
        counts: Dict[str, dict] = {}
        for job in self.all_jobs:
            jd = job.get("job_data", job)
            job_name = jd.get("job_name", "unknown")
            for comp in jd.get("components", []):
                ctype = comp.get("component_type", "UNKNOWN") if isinstance(comp, dict) else str(comp)
                if ctype not in counts:
                    counts[ctype] = {"name": ctype, "type": "component", "count": 0, "jobs": []}
                counts[ctype]["count"] += 1
                if job_name not in counts[ctype]["jobs"]:
                    counts[ctype]["jobs"].append(job_name)
        return sorted(counts.values(), key=lambda x: x["count"], reverse=True)

    def _routine_catalog(self) -> List[dict]:
        try:
            data = analyze_routines(self.all_jobs)
            catalog = []
            for r in data.get("routines", []):
                catalog.append({
                    "name": r.get("name", "?"),
                    "language": r.get("language", "Java"),
                    "used_in": r.get("jobs_using", r.get("used_in", [])),
                })
            return catalog
        except Exception:
            logger.exception("Failed to build routine catalog knowledge.")
            return []

    def _joblet_catalog(self) -> List[dict]:
        try:
            data = analyze_joblets(self.all_jobs)
            catalog = []
            for j in data.get("joblets", []):
                catalog.append({
                    "name": j.get("name", "?"),
                    "used_in": j.get("jobs_using", j.get("used_in", [])),
                })
            return catalog
        except Exception:
            logger.exception("Failed to build joblet catalog knowledge.")
            return []

    def _dependency_catalog(self) -> List[dict]:
        try:
            data = analyze_dependencies(self.all_jobs)
            catalog = []
            for dep in data.get("dependencies", []):
                catalog.append({
                    "job": dep.get("job", dep.get("source", "?")),
                    "depends_on": dep.get("depends_on", dep.get("targets", [])),
                    "called_by": dep.get("called_by", dep.get("sources", [])),
                })
            return catalog
        except Exception:
            logger.exception("Failed to build dependency catalog from analyzer; using fallback detection.")
            catalog = []
            job_names = [job.get("job_data", job).get("job_name", "?") for job in self.all_jobs]
            for job in self.all_jobs:
                jd = job.get("job_data", job)
                deps = [c.get("component_parameter", {}).get("JOB_NAME", "")
                        for c in jd.get("components", [])
                        if isinstance(c, dict) and c.get("component_type") == "tRunJob"]
                deps = [d for d in deps if d and d in job_names]
                if deps:
                    catalog.append({"job": jd.get("job_name", "?"), "depends_on": deps, "called_by": []})
            return catalog

    def _duplicate_artifacts(self) -> List[dict]:
        """Detect jobs sharing identical component-type fingerprints (likely copies or duplicates)."""
        from collections import defaultdict
        fingerprints: dict = defaultdict(list)
        for job in self.all_jobs:
            jd = job.get("job_data", job)
            job_name = jd.get("job_name", "unknown")
            components = jd.get("components", [])
            types = tuple(sorted(
                c.get("component_type", "UNKNOWN") if isinstance(c, dict) else str(c)
                for c in components
            ))
            key = (len(components), types)
            fingerprints[key].append(job_name)
        duplicates = []
        for (count, types), jobs in fingerprints.items():
            if len(jobs) > 1:
                duplicates.append({
                    "component_count": count,
                    "component_signature": list(types),
                    "jobs": jobs,
                    "duplicate_count": len(jobs),
                })
        return sorted(duplicates, key=lambda x: -x["duplicate_count"])

    def _migration_playbook(self) -> List[dict]:
        playbook = []
        for job in self.all_jobs:
            jd = job.get("job_data", job)
            risk = jd.get("risk_level", job.get("migration_risk", "MEDIUM"))
            priority = "HIGH" if risk in ("HIGH", "CRITICAL") else ("LOW" if risk == "LOW" else "MEDIUM")
            components = jd.get("components", [])
            has_java = any(
                (c.get("component_type", "") if isinstance(c, dict) else str(c)) in {"tJava", "tJavaRow", "tJavaFlex"}
                for c in components
            )
            steps = ["Validate source repository export",
                     "Run Talend migration check tool",
                     "Import into Talend 8 Studio",
                     "Resolve context variable references",
                     "Test job execution"]
            if has_java:
                steps.insert(3, "Review and update custom Java code")
            playbook.append({
                "job": jd.get("job_name", "?"),
                "priority": priority,
                "effort": f"{len(components) // 5 + 1}d",
                "steps": steps,
            })
        return sorted(playbook, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x["priority"], 1))
