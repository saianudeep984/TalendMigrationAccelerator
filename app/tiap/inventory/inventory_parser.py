import os
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence

from app.analyzers.complexity_analyzer import calculate_complexity
from app.tiap.models.repository import (
    build_adjacency_from_jobs,
    component_parameters,
    inventory_reference_sets,
    iter_job_data,
    load_jobs_from_repository,
    normalize_name,
    scan_repository_files,
    write_json,
)


class InventoryParser:
    def build_inventory(
        self,
        all_jobs: Optional[Sequence[Dict[str, Any]]] = None,
        repository_path: Optional[str] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        jobs = list(all_jobs or [])
        files = scan_repository_files(repository_path) if repository_path else {
            "joblets": [], "contexts": [], "routines": [], "metadata": []
        }
        if not jobs and repository_path:
            jobs = load_jobs_from_repository(repository_path)

        adjacency = build_adjacency_from_jobs(jobs)
        child_jobs = {child for children in adjacency.values() for child in children}
        parent_jobs = {parent for parent, children in adjacency.items() if children}
        known_jobs = {normalize_name(data.get("job_name")) for data in iter_job_data(jobs)}
        orphan_jobs = sorted(job for job in known_jobs if job not in child_jobs and job not in parent_jobs)

        component_counts: Counter = Counter()
        context_counts: Counter = Counter()
        connection_counts: Counter = Counter()
        schema_counts: Counter = Counter()
        metadata_counts: Counter = Counter()
        job_rows: List[Dict[str, Any]] = []
        refs = inventory_reference_sets(jobs)

        for data in iter_job_data(jobs):
            job_name = normalize_name(data.get("job_name", "Unknown"))
            components = []
            metadata_refs = set()
            routines = set()
            joblets = set()
            contexts = set()

            for ctx in data.get("contexts", []):
                if isinstance(ctx, dict) and ctx.get("name"):
                    contexts.add(str(ctx["name"]))
                    context_counts[str(ctx["name"])] += 1

            for component in data.get("components", []):
                if not isinstance(component, dict):
                    continue
                ctype = component.get("component_type", "UNKNOWN_COMPONENT")
                component_counts[ctype] += 1
                params = component_parameters(component)
                components.append({
                    "component_type": ctype,
                    "unique_name": component.get("unique_name", ""),
                    "parameters": params,
                })
                if ctype.lower().startswith("tjoblet") or ctype == "tJoblet":
                    joblets.add(params.get("JOBLET") or params.get("PROCESS") or component.get("unique_name") or ctype)
                for key, value in params.items():
                    text = str(value)
                    if "metadata" in text.lower() or "repository" in text.lower():
                        metadata_refs.add(normalize_name(text.split("/")[-1]))
                    if key in ("SCHEMA", "SCHEMA_REPOSITORY", "PROPERTY"):
                        schema_counts[normalize_name(text)] += 1
                    if "context." in text:
                        import re
                        contexts.update(re.findall(r"context\.([A-Za-z_][A-Za-z0-9_]*)", text))
                    import re
                    routines.update(re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", text))

            for conn in data.get("connections", []):
                connector = conn.get("connector") if isinstance(conn, dict) else str(conn)
                if connector:
                    connection_counts[connector] += 1

            complexity = calculate_complexity(data)
            job_rows.append({
                "job_name": job_name,
                "components": components,
                "contexts": sorted(contexts),
                "joblets": sorted(joblets),
                "routines": sorted(routines),
                "metadata": sorted(metadata_refs),
                "parent_jobs": sorted(parent for parent, children in adjacency.items() if job_name in children),
                "child_jobs": sorted(adjacency.get(job_name, set())),
                "complexity_score": complexity.get("score", 0),
                "complexity": complexity.get("complexity", "LOW"),
                "connections": data.get("connections", []),
                "schemas": sorted(schema_counts),
            })
            metadata_counts.update(metadata_refs)

        joblet_names = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("joblets", [])}
        routine_names = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("routines", [])}
        metadata_names = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("metadata", [])}
        context_names = {normalize_name(os.path.basename(p).replace(".item", "")) for p in files.get("contexts", [])}

        inventory = {
            "kpis": {
                "total_jobs": len(job_rows),
                "total_components": sum(component_counts.values()),
                "total_contexts": len(context_names or set(context_counts)),
                "total_joblets": len(joblet_names or refs["joblets"]),
                "total_routines": len(routine_names or refs["routines"]),
                "total_metadata": len(metadata_names or set(metadata_counts)),
                "total_parent_jobs": len(parent_jobs),
                "total_child_jobs": len(child_jobs & known_jobs),
                "total_orphan_jobs": len(orphan_jobs),
            },
            "jobs": sorted(job_rows, key=lambda item: item["job_name"]),
            "components": dict(sorted(component_counts.items())),
            "contexts": dict(sorted(context_counts.items())),
            "joblets": sorted(joblet_names or refs["joblets"]),
            "routines": sorted(routine_names or refs["routines"]),
            "metadata": sorted(metadata_names or set(metadata_counts)),
            "dependencies": {parent: sorted(children) for parent, children in sorted(adjacency.items())},
            "connections": dict(sorted(connection_counts.items())),
            "schemas": dict(sorted(schema_counts.items())),
            "orphan_jobs": orphan_jobs,
        }
        if output_dir:
            write_json(os.path.join(output_dir, "repository_inventory.json"), inventory)
        return inventory


def build_inventory(all_jobs=None, repository_path=None, output_dir=None):
    return InventoryParser().build_inventory(all_jobs, repository_path, output_dir)
