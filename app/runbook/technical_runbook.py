from __future__ import annotations
from app.upgrade_advisor.upgrade_inventory import components, ctype, job_data


class TechnicalMigrationRunbook:
    def generate(self, jobs, upgrade=None):
        dep = (upgrade or {}).get("deprecated_components", {}).get("findings", [])
        dep_by_job = {}
        for f in dep: dep_by_job.setdefault(f["job_name"], []).append(f)
        activities = []
        for j in jobs or []:
            name = job_data(j).get("job_name") or j.get("job_name")
            fixes = dep_by_job.get(name, [])
            activities.append({"job_name": name, "component_fixes": fixes,
                               "upgrade_steps": [f"Review {len(components(j))} components", "Apply mappings", "Build in Talend 8"],
                               "validation_procedures": ["Schema validation", "Row count reconciliation", "Error flow test"],
                               "testing_activities": ["Unit test", "Regression test"], "deployment_activities": ["Package", "Deploy", "Schedule"]})
        return {"job_by_job_activities": activities}
