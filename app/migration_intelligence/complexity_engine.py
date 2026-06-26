"""Project and job migration complexity scoring."""
from collections import Counter
from app.analyzers.complexity_analyzer import calculate_complexity


def _data(job):
    return job.get("job_data", job) if isinstance(job, dict) else {}


class MigrationComplexityEngine:
    """Extends the canonical component scorer with repository-level factors."""

    FACTOR_WEIGHTS = {
        "subjobs": 6, "tmaps": 4, "custom_java": 12, "routines": 7,
        "contexts": 2, "dependencies": 5, "unsupported_components": 15,
    }

    @staticmethod
    def level(score):
        return "LOW" if score < 50 else "MEDIUM" if score < 100 else "HIGH" if score < 200 else "CRITICAL"

    def score_job(self, job):
        data = _data(job)
        components = data.get("components", []) or []
        types = [c.get("component_type", "") if isinstance(c, dict) else str(c) for c in components]
        dependencies = job.get("dependencies", {}) if isinstance(job, dict) else {}
        unsupported = (job.get("unsupported_components", []) or job.get("unsupported", [])) if isinstance(job, dict) else []
        routines = dependencies.get("routines", data.get("routines", [])) or []
        contexts = dependencies.get("contexts", data.get("contexts", [])) or []
        children = dependencies.get("child_jobs", data.get("child_jobs", [])) or []
        base = calculate_complexity(data)
        factors = {
            "components": len(components), "subjobs": len(children),
            "tmaps": sum(t in {"tMap", "tXMLMap", "tELTMap"} for t in types),
            "custom_java": sum(t in {"tJava", "tJavaRow", "tJavaFlex", "tJavaInput", "tJavaOutput"} for t in types),
            "routines": len(set(map(str, routines))), "contexts": len(contexts),
            "dependencies": len(set(map(str, children))), "unsupported_components": len(unsupported),
        }
        score = base["score"] + sum(factors[k] * w for k, w in self.FACTOR_WEIGHTS.items())
        return {"job_name": data.get("job_name", "Unknown"), "score": score,
                "complexity": self.level(score), "complexity_band": self.level(score),
                "factors": factors, "risk_factors": base.get("risk_factors", [])}

    def analyze_project(self, jobs):
        results = [self.score_job(j) for j in jobs or []]
        total = sum(r["score"] for r in results)
        # Portfolio size contributes without making a large set of trivial jobs invisible.
        score = round(total / len(results) + max(0, len(results) - 1) * 2) if results else 0
        distribution = Counter(r["complexity"] for r in results)
        return {"score": score, "complexity": self.level(score), "job_count": len(results),
                "distribution": {k: distribution.get(k, 0) for k in ("LOW", "MEDIUM", "HIGH", "CRITICAL")},
                "jobs": results}

    analyze = analyze_project


def calculate_migration_complexity(jobs):
    return MigrationComplexityEngine().analyze_project(jobs)
