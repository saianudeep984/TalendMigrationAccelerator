import json
import os

_DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompts.json")

_HARDCODED_DEFAULTS = {
    "executive_summary": "You are a Talend migration expert. Given this repository data, write a concise executive summary covering: business impact, migration complexity, risk level, and recommended approach. Return markdown.",
    "technical_doc": "You are a Talend migration expert. Given this job metadata, produce technical documentation covering: components used, data flow, connection details, transformation logic. Return markdown.",
    "functional_doc": "You are a Talend migration expert. Given this job metadata, produce functional documentation covering: business purpose, source/target systems, data processed, business rules. Return markdown.",
    "kt_doc": "You are a Talend migration expert. Given this job metadata, produce a knowledge transfer document covering: job purpose, execution steps, dependencies, known issues, runbook. Return markdown.",
    "migration_assessment": "You are a Talend migration expert. Given this repository data, produce a migration assessment covering: readiness score, blockers, effort estimate, risk matrix, recommended migration order. Return markdown.",
    "test_cases": "You are a Talend migration expert. Given this job metadata, generate test cases as a markdown table with columns: Test ID | Test Name | Input | Expected Output | Pass Criteria.",
    "recommendations": "You are a Talend migration expert. Given this repository analysis, provide prioritized migration recommendations covering: quick wins, critical blockers, refactoring needs, cloud readiness. Return markdown.",
    "routine_assessment": "You are a Talend migration expert. Given these routines, assess each for: complexity, reuse count, migration risk, and recommended action. Return a markdown summary.",
    "joblet_assessment": "You are a Talend migration expert. Given these joblets, assess each for: usage across jobs, migration risk, and whether to keep, refactor, or replace. Return a markdown summary.",
    "java_risk": "You are a Talend migration expert. Given these Java components and routines, identify: deprecated APIs, Java version incompatibilities, cloud-unsafe patterns, and remediation steps. Return markdown.",
}


class PromptStore:

    def load(self) -> dict:
        path = os.path.abspath(_DEFAULTS_PATH)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return dict(_HARDCODED_DEFAULTS)

    def save(self, key: str, value: str) -> None:
        prompts = self.load()
        prompts[key] = value
        path = os.path.abspath(_DEFAULTS_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2)

    def reset(self, key: str) -> None:
        prompts = self.load()
        prompts[key] = _HARDCODED_DEFAULTS.get(key, "")
        path = os.path.abspath(_DEFAULTS_PATH)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2)

    def get(self, key: str) -> str:
        return self.load().get(key, _HARDCODED_DEFAULTS.get(key, ""))
