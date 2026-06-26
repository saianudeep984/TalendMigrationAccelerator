"""Table/column downstream blast-radius reports."""
from app.lineage.advanced_lineage_engine import AdvancedLineageEngine


class DataImpactAnalyzer:
    def analyze(self, lineage, table, column=None):
        nodes = {n["id"]: n for n in lineage.get("nodes", [])}
        selected = [n["id"] for n in nodes.values() if n.get("table", "").lower() == table.lower()
                    and (not column or n.get("column", "").lower() == column.lower())]
        impacted = set()
        for node_id in selected: impacted.update(AdvancedLineageEngine.trace(lineage, node_id))
        assets = [nodes[n] for n in impacted if n in nodes]
        jobs = sorted({n.get("job_name") for n in assets if n.get("job_name")})
        targets = sorted({f"{n.get('table')}.{n.get('column')}" for n in assets if n.get("kind") in {"target", "repository_metadata"}})
        reports = sorted({n.get("metadata", {}).get("report") for n in assets if n.get("metadata", {}).get("report")})
        datasets = sorted({n.get("metadata", {}).get("dataset") for n in assets if n.get("metadata", {}).get("dataset")})
        return {"selection": {"table": table, "column": column}, "matched_assets": selected,
                "downstream_assets": sorted(impacted), "downstream_jobs": jobs, "affected_targets": targets,
                "impacted_reports": reports, "impacted_datasets": datasets,
                "impact_count": len(impacted), "report": self._report(table, column, jobs, targets, reports, datasets)}

    @staticmethod
    def _report(table, column, jobs, targets, reports, datasets):
        asset = f"{table}.{column}" if column else table
        return (f"Impact analysis for {asset}: {len(jobs)} downstream jobs, {len(targets)} targets, "
                f"{len(reports)} reports and {len(datasets)} datasets are affected.")

    analyze_impact = analyze
