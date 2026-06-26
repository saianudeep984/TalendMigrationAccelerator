"""Topologically safe migration wave planning."""
import networkx as nx


class MigrationWavePlanner:
    def plan(self, jobs, graph, max_wave_size=None):
        job_names = set(graph.get("job_names", []))
        by_name = {j.get("job_name"): j for j in (jobs.get("jobs", []) if isinstance(jobs, dict) else jobs or [])}
        g = nx.DiGraph(); g.add_nodes_from(job_names)
        # A parent calling a child depends on that child; reverse execution edges for migration order.
        for edge in graph.get("edges", []):
            if edge["source"] in job_names and edge["target"] in job_names:
                g.add_edge(edge["target"], edge["source"])
        cycles = [sorted(c) for c in nx.strongly_connected_components(g) if len(c) > 1]
        if cycles:
            condensed = nx.condensation(g)
            members = nx.get_node_attributes(condensed, "members")
            generations = [[n for group in generation for n in sorted(members[group])]
                           for generation in nx.topological_generations(condensed)]
        else:
            generations = [sorted(x) for x in nx.topological_generations(g)]
        waves = []
        for generation in generations:
            generation.sort(key=lambda n: (self._priority(by_name.get(n, {})), n))
            chunks = [generation[i:i + max_wave_size] for i in range(0, len(generation), max_wave_size)] if max_wave_size else [generation]
            for chunk in chunks:
                number = len(waves) + 1
                waves.append({"wave": number, "name": f"Wave {number}", "jobs": chunk,
                              "estimated_complexity": [by_name.get(n, {}).get("complexity", "LOW") for n in chunk]})
        assignment = {job: wave["wave"] for wave in waves for job in wave["jobs"]}
        return {"waves": waves, "assignment": assignment, "cycles": cycles,
                "valid": all(assignment.get(e["target"], 0) <= assignment.get(e["source"], 0)
                             for e in graph.get("edges", []) if e["source"] in job_names and e["target"] in job_names)}

    @staticmethod
    def _priority(job):
        level = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(job.get("complexity", "LOW"), 0)
        readiness = job.get("readiness_score", 100)
        risk = job.get("risk_score", level * 25)
        return (level + risk / 100 - readiness / 100)

    plan_waves = plan
