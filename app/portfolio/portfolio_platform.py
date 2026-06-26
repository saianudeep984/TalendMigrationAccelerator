"""Enterprise Portfolio Platform.

Aggregates multi-project Talend migration intelligence without duplicating
readiness, architecture, impact, lineage, or migration scoring engines.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from app.analyzers.migration_readiness_score import calculate_migration_readiness_score
from app.architecture.architecture_assessor import ArchitectureAssessmentEngine
from app.architecture.technical_debt_engine import TechnicalDebtEngine
from app.impact_analysis.engine import ImpactLineageIntelligenceEngine
from app.migration_intelligence.engine import MigrationIntelligenceEngine
from app.migration_intelligence.wave_planner import MigrationWavePlanner


def _project_name(project: Any, idx: int) -> str:
    if isinstance(project, Mapping):
        return str(project.get("project_name") or project.get("name") or project.get("id") or f"Project {idx + 1}")
    return f"Project {idx + 1}"


def _project_jobs(project: Any) -> List[Dict[str, Any]]:
    if isinstance(project, Mapping):
        jobs = project.get("jobs") or project.get("items") or project.get("analysis_jobs") or []
        return [_normalize_job(j) for j in list(jobs or [])]
    return [_normalize_job(j) for j in list(project or [])]


def _normalize_job(job: Any) -> Dict[str, Any]:
    if not isinstance(job, Mapping):
        return {"job_name": str(job), "components": [], "job_data": {"job_name": str(job), "components": []}}
    data = dict(job)
    jd = dict(data.get("job_data") or {})
    name = data.get("job_name") or data.get("name") or jd.get("job_name") or "Unnamed Job"
    comps = data.get("components") or jd.get("components") or []
    norm = []
    for comp in comps:
        c = dict(comp or {})
        comp_type = c.get("component_type") or c.get("type") or c.get("componentName") or c.get("name") or ""
        c["component_type"] = comp_type
        c.setdefault("type", comp_type)
        c.setdefault("componentName", comp_type)
        norm.append(c)
    data["job_name"] = name
    data["components"] = norm
    jd["job_name"] = name
    jd["components"] = norm
    data["job_data"] = jd
    return data


def _score(readiness: Any) -> float:
    if isinstance(readiness, Mapping):
        for key in ("overall_score", "readiness_score", "score"):
            if key in readiness:
                return float(readiness[key] or 0)
    return float(getattr(readiness, "overall_score", 0) or getattr(readiness, "readiness_score", 0) or 0)


def _risk_band(score: float) -> str:
    if score >= 80:
        return "LOW"
    if score >= 60:
        return "MEDIUM"
    if score >= 40:
        return "HIGH"
    return "CRITICAL"


@dataclass
class PortfolioConfig:
    hourly_rate: float = 125.0
    max_wave_size: int = 25
    program_team_capacity_hours_per_week: float = 320.0


class EnterprisePortfolioPlatform:
    """Portfolio-level orchestration for CIO, architects, and program teams."""

    def __init__(self, config: Optional[PortfolioConfig] = None):
        self.config = config or PortfolioConfig()
        self.migration_engine = MigrationIntelligenceEngine()
        self.impact_engine = ImpactLineageIntelligenceEngine()
        self.architecture_engine = ArchitectureAssessmentEngine()

    def analyze(self, projects: Iterable[Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        if config:
            self.config = PortfolioConfig(**{**self.config.__dict__, **dict(config)})
        project_results = [self._analyze_project(project, i) for i, project in enumerate(projects or [])]
        dependencies = self._portfolio_dependencies(project_results)
        risks = self._cross_project_risks(project_results, dependencies)
        waves = self._wave_plan(project_results, dependencies)
        effort = self._portfolio_effort(project_results, waves)
        debt = self._portfolio_debt(project_results)
        roadmap = self._roadmap(waves, effort, risks)
        kpis = self._kpis(project_results, effort, risks, debt)
        dashboards = self._dashboards(project_results, effort, risks, debt, roadmap, kpis, dependencies, waves)
        return {
            "summary": self._summary(project_results, effort, risks, debt),
            "projects": project_results,
            "readiness_dashboard": self._readiness_dashboard(project_results),
            "migration_effort": effort,
            "cross_project_risks": risks,
            "organization_roadmap": roadmap,
            "executive_portfolio_report": dashboards["executive"],
            "cio_dashboard": dashboards["cio"],
            "architect_dashboard": dashboards["architect"],
            "program_management_dashboard": dashboards["program"],
            "wave_planning": waves,
            "dependency_analysis": dependencies,
            "technical_debt_analysis": debt,
            "cost_estimation": effort["cost"],
            "kpi_tracking": kpis,
        }

    def _analyze_project(self, project: Any, idx: int) -> Dict[str, Any]:
        name = _project_name(project, idx)
        jobs = _project_jobs(project)
        readiness_obj = calculate_migration_readiness_score(jobs, {}, [])
        readiness = readiness_obj.__dict__ if hasattr(readiness_obj, "__dict__") else readiness_obj
        migration = self.migration_engine.analyze(jobs, readiness, None)
        impact = self.impact_engine.analyze(jobs, migration_intelligence=migration, readiness=readiness)
        architecture = self.architecture_engine.analyze(jobs, readiness, migration, impact)
        effort = migration.get("effort_estimate") or migration.get("effort") or self._fallback_effort(architecture, jobs)
        score = _score(readiness)
        return {
            "project_name": name,
            "job_count": len(jobs),
            "readiness": readiness,
            "readiness_score": round(score, 1),
            "risk_band": _risk_band(score),
            "migration_intelligence": migration,
            "impact_intelligence": impact,
            "architecture": architecture,
            "technical_debt": architecture.get("technical_debt") or TechnicalDebtEngine().calculate(architecture.get("anti_patterns", {}), migration),
            "effort": effort,
            "estimated_hours": float(effort.get("estimated_hours", 0) or 0),
        }

    @staticmethod
    def _fallback_effort(architecture: Mapping[str, Any], jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        debt = architecture.get("technical_debt", {})
        hours = round(len(jobs) * 12 + float(debt.get("debt_score", 0)) * max(1, len(jobs)) / 4, 1)
        return {"estimated_hours": hours, "estimated_days": round(hours / 8, 1), "estimated_weeks": round(hours / 40, 1)}

    def _portfolio_dependencies(self, projects: List[Dict[str, Any]]) -> Dict[str, Any]:
        component_index: Dict[str, set] = defaultdict(set)
        edges = []
        for project in projects:
            pname = project["project_name"]
            graph = project["migration_intelligence"].get("dependency_graph", {})
            for node in graph.get("nodes", []):
                label = str(node.get("label") or node.get("id") or "")
                if label:
                    component_index[label].add(pname)
            for edge in graph.get("edges", []):
                edges.append({"project": pname, **edge})
        shared = [{"asset": k, "projects": sorted(v), "project_count": len(v)} for k, v in component_index.items() if len(v) > 1]
        return {
            "project_count": len(projects),
            "intra_project_edges": edges,
            "shared_assets": sorted(shared, key=lambda x: (-x["project_count"], x["asset"])),
            "cross_project_dependency_count": len(shared),
        }

    @staticmethod
    def _cross_project_risks(projects: List[Dict[str, Any]], dependencies: Mapping[str, Any]) -> Dict[str, Any]:
        items = []
        for p in projects:
            debt_score = float(p.get("technical_debt", {}).get("debt_score", 0) or 0)
            readiness = float(p.get("readiness_score", 0) or 0)
            deprecated = p.get("impact_intelligence", {}).get("deprecated_components", {}).get("summary", {}).get("total", 0)
            risk_score = round((100 - readiness) * .45 + debt_score * .35 + min(30, deprecated * 3), 1)
            items.append({"project_name": p["project_name"], "risk_score": risk_score, "risk_band": _risk_band(100 - risk_score), "deprecated_findings": deprecated})
        blockers = [x for x in items if x["risk_score"] >= 60]
        return {
            "portfolio_risk_score": round(sum(x["risk_score"] for x in items) / max(1, len(items)), 1),
            "highest_risk_projects": sorted(items, key=lambda x: x["risk_score"], reverse=True)[:10],
            "shared_asset_risks": dependencies.get("shared_assets", [])[:10],
            "blockers": blockers,
        }

    def _wave_plan(self, projects: List[Dict[str, Any]], dependencies: Mapping[str, Any]) -> Dict[str, Any]:
        jobs = [{"job_name": p["project_name"], "complexity": p["risk_band"], "readiness_score": p["readiness_score"], "risk_score": 100 - p["readiness_score"]} for p in projects]
        graph = {"job_names": [j["job_name"] for j in jobs], "edges": []}
        shared = dependencies.get("shared_assets", [])
        for asset in shared:
            ps = asset.get("projects", [])
            for source, target in zip(ps, ps[1:]):
                graph["edges"].append({"source": target, "target": source, "type": "shared_asset", "asset": asset["asset"]})
        plan = MigrationWavePlanner().plan(jobs, graph, max_wave_size=self.config.max_wave_size)
        plan["portfolio_wave_count"] = len(plan.get("waves", []))
        return plan

    def _portfolio_effort(self, projects: List[Dict[str, Any]], waves: Mapping[str, Any]) -> Dict[str, Any]:
        total_hours = round(sum(float(p.get("estimated_hours", 0) or 0) for p in projects), 1)
        contingency = round(total_hours * .18, 1)
        total_with_contingency = round(total_hours + contingency, 1)
        wave_hours = []
        by_name = {p["project_name"]: p for p in projects}
        for wave in waves.get("waves", []):
            hours = round(sum(by_name.get(name, {}).get("estimated_hours", 0) for name in wave.get("jobs", [])), 1)
            wave_hours.append({"wave": wave.get("wave"), "projects": wave.get("jobs", []), "estimated_hours": hours})
        return {
            "estimated_hours": total_hours,
            "contingency_hours": contingency,
            "total_hours_with_contingency": total_with_contingency,
            "estimated_weeks": round(total_with_contingency / max(1, self.config.program_team_capacity_hours_per_week), 1),
            "by_project": [{"project_name": p["project_name"], "estimated_hours": p["estimated_hours"]} for p in projects],
            "by_wave": wave_hours,
            "cost": {
                "hourly_rate": self.config.hourly_rate,
                "labor_cost": round(total_hours * self.config.hourly_rate, 2),
                "contingency_cost": round(contingency * self.config.hourly_rate, 2),
                "total_cost": round(total_with_contingency * self.config.hourly_rate, 2),
            },
        }

    @staticmethod
    def _portfolio_debt(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
        items = []
        for p in projects:
            debt = p.get("technical_debt", {})
            items.append({"project_name": p["project_name"], "debt_score": debt.get("debt_score", 0), "debt_hours": debt.get("estimated_remediation_hours", 0), "top_items": debt.get("prioritized_remediation", [])[:5]})
        return {
            "portfolio_debt_score": round(sum(float(x["debt_score"] or 0) for x in items) / max(1, len(items)), 1),
            "estimated_remediation_hours": round(sum(float(x["debt_hours"] or 0) for x in items), 1),
            "highest_debt_projects": sorted(items, key=lambda x: x["debt_score"], reverse=True)[:10],
        }

    @staticmethod
    def _readiness_dashboard(projects: List[Dict[str, Any]]) -> Dict[str, Any]:
        bands = Counter(p["risk_band"] for p in projects)
        scores = [p["readiness_score"] for p in projects]
        return {
            "portfolio_readiness_score": round(sum(scores) / max(1, len(scores)), 1),
            "risk_band_distribution": dict(bands),
            "ready_projects": [p["project_name"] for p in projects if p["readiness_score"] >= 80],
            "needs_remediation": [p["project_name"] for p in projects if p["readiness_score"] < 60],
        }

    @staticmethod
    def _roadmap(waves: Mapping[str, Any], effort: Mapping[str, Any], risks: Mapping[str, Any]) -> Dict[str, Any]:
        roadmap = []
        week = 1
        for wave in effort.get("by_wave", []):
            duration = max(1, round(float(wave.get("estimated_hours", 0) or 0) / 320))
            roadmap.append({"wave": wave["wave"], "projects": wave["projects"], "start_week": week, "end_week": week + duration - 1, "focus": "Remediate and migrate"})
            week += duration
        return {"timeline": roadmap, "critical_blockers": risks.get("blockers", []), "dependency_cycles": waves.get("cycles", [])}

    @staticmethod
    def _kpis(projects: List[Dict[str, Any]], effort: Mapping[str, Any], risks: Mapping[str, Any], debt: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "projects_analyzed": len(projects),
            "jobs_analyzed": sum(p["job_count"] for p in projects),
            "average_readiness": round(sum(p["readiness_score"] for p in projects) / max(1, len(projects)), 1),
            "portfolio_risk_score": risks.get("portfolio_risk_score", 0),
            "portfolio_debt_score": debt.get("portfolio_debt_score", 0),
            "estimated_hours": effort.get("total_hours_with_contingency", 0),
            "estimated_cost": effort.get("cost", {}).get("total_cost", 0),
            "waves": len(effort.get("by_wave", [])),
        }

    @staticmethod
    def _summary(projects: List[Dict[str, Any]], effort: Mapping[str, Any], risks: Mapping[str, Any], debt: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "project_count": len(projects),
            "job_count": sum(p["job_count"] for p in projects),
            "portfolio_risk_score": risks.get("portfolio_risk_score", 0),
            "portfolio_debt_score": debt.get("portfolio_debt_score", 0),
            "estimated_hours": effort.get("total_hours_with_contingency", 0),
            "estimated_cost": effort.get("cost", {}).get("total_cost", 0),
        }

    @staticmethod
    def _dashboards(projects, effort, risks, debt, roadmap, kpis, dependencies, waves):
        executive = {"summary": kpis, "roadmap": roadmap, "top_risks": risks.get("highest_risk_projects", [])[:5], "cost": effort.get("cost", {})}
        cio = {"investment": effort.get("cost", {}), "risk": risks, "kpis": kpis, "roadmap": roadmap}
        architect = {"dependency_analysis": dependencies, "technical_debt": debt, "project_architecture": [{"project_name": p["project_name"], "scorecard": p["architecture"].get("scorecard", {})} for p in projects]}
        program = {"waves": waves, "effort_by_wave": effort.get("by_wave", []), "blockers": risks.get("blockers", []), "kpis": kpis}
        return {"executive": executive, "cio": cio, "architect": architect, "program": program}


def analyze_portfolio(projects: Iterable[Any], config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    return EnterprisePortfolioPlatform().analyze(projects, config)
