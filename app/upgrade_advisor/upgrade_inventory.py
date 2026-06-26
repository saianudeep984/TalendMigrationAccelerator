from __future__ import annotations
from collections import Counter
from typing import Any, Dict, Iterable, Mapping


def job_data(job): return (job or {}).get("job_data", job or {})
def components(job): return job_data(job).get("components", (job or {}).get("components", [])) or []
def ctype(comp): return comp.get("component_type") or comp.get("type") or comp.get("componentName") or comp.get("name") or ""


class UpgradeInventoryEngine:
    def analyze(self, jobs: Iterable[Mapping[str, Any]], source_version="Talend 7.x", target_version="Talend 8.x") -> Dict[str, Any]:
        jobs = list(jobs or [])
        types = Counter(ctype(c) for j in jobs for c in components(j))
        joblets = sum(1 for t in types if "Joblet" in t or t.startswith("tJoblet"))
        routes = sum(v for t, v in types.items() if "Route" in t or t in {"cTimer", "cMQConnectionFactory"})
        services = sum(v for t, v in types.items() if "Service" in t or t in {"tRESTRequest", "tSOAP", "tWebService"})
        contexts = sum(v for t, v in types.items() if t in {"tContextLoad", "tContextDump"})
        metadata = sum(v for t, v in types.items() if any(x in t for x in ("DB", "Mysql", "Oracle", "JDBC", "File", "S3", "Azure", "Snowflake")))
        routines = sum(v for t, v in types.items() if t in {"tJava", "tJavaRow", "tJavaFlex", "tBeanShell", "tGroovy"})
        sql = sum(v for t, v in types.items() if t.endswith("Row") or "SQL" in t or "DB" in t)
        custom_java = sum(v for t, v in types.items() if t in {"tJava", "tJavaRow", "tJavaFlex", "tBeanShell", "tGroovy"})
        framework_assets = sum(v for t, v in types.items() if t in {"tLogCatcher", "tStatCatcher", "tDie", "tWarn", "tRunJob", "tContextLoad", "tPrejob", "tPostjob"})
        return {
            "source_version": source_version, "target_version": target_version,
            "project_inventory": {"jobs": len(jobs), "joblets": joblets, "routes": routes, "services": services,
                "context_groups": contexts, "metadata_connections": metadata, "routines": routines,
                "sql_assets": sql, "custom_java": custom_java, "framework_assets": framework_assets,
                "component_distribution": dict(types)},
            "job_inventory": [{"job_name": job_data(j).get("job_name") or j.get("job_name") or f"Job {i+1}",
                "component_count": len(components(j)), "components": [ctype(c) for c in components(j)],
                "custom_java": sum(ctype(c) in {"tJava", "tJavaRow", "tJavaFlex", "tBeanShell", "tGroovy"} for c in components(j))}
                for i, j in enumerate(jobs)]
        }
