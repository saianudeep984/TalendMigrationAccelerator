"""End-to-end and cross-job column lineage built on canonical parser output."""
from collections import defaultdict, deque
from dataclasses import asdict, is_dataclass
from pathlib import Path
from app.lineage.transformation_intelligence import TransformationIntelligence


def _dict(value):
    return asdict(value) if is_dataclass(value) else dict(value) if isinstance(value, dict) else vars(value)


class AdvancedLineageEngine:
    def build(self, jobs, mappings_by_job=None, repository_metadata=None):
        mappings_by_job = mappings_by_job or {}; repository_metadata = repository_metadata or []
        nodes, edges, transformations = {}, [], []
        for wrapper in jobs or []:
            data = wrapper.get("job_data", wrapper); job = data.get("job_name", "Unknown")
            mappings = mappings_by_job.get(job)
            rules = data.get("mapping_rules", wrapper.get("mapping_rules", [])) or []
            if mappings is None:
                mappings = data.get("column_mappings", wrapper.get("column_mappings"))
            if mappings is None: mappings, rules = self._parse(wrapper, rules)
            mappings = mappings or []
            tx = TransformationIntelligence().extract(mappings, rules, data.get("components", []), job)
            transformations.extend(tx["transformations"])
            for raw in mappings:
                item = _dict(raw)
                source = self._node(job, item, "source", nodes); target = self._node(job, item, "target", nodes)
                if source and target:
                    edges.append({"source": source, "target": target, "type": item.get("rule_type", "mapping"),
                                  "expression": item.get("expression", ""), "job_name": job,
                                  "component": item.get("source_component", "")})
        self._add_cross_job(nodes, edges)
        for item in repository_metadata:
            raw = _dict(item); node_id = self.asset_id(raw.get("table", ""), raw.get("column", ""), raw.get("job_name", "repository"))
            nodes.setdefault(node_id, {"id": node_id, "job_name": raw.get("job_name", "repository"), "table": raw.get("table", ""),
                                      "column": raw.get("column", ""), "kind": "repository_metadata", "metadata": raw})
            key = (raw.get("table", "").lower(), raw.get("column", "").lower())
            for other_id, other in list(nodes.items()):
                if other_id != node_id and key == (other.get("table", "").lower(), other.get("column", "").lower()):
                    edges.append({"source": node_id, "target": other_id, "type": "repository_metadata",
                                  "expression": "", "job_name": other.get("job_name", "")})
        return {"nodes": list(nodes.values()), "edges": self._dedupe(edges), "transformations": transformations,
                "adjacency": self._adjacency(edges), "reverse_adjacency": self._adjacency(edges, reverse=True)}

    build_lineage = build

    @staticmethod
    def _parse(wrapper, rules):
        path = wrapper.get("file_path", "")
        if not path or not Path(path).is_file(): return [], rules
        from app.cache.cache_manager import CacheManager as _CM
        _cm = _CM()
        job_data = _cm.load_or_parse(path)
        return job_data.get("column_mappings", []) or [], job_data.get("mapping_rules", []) or rules

    def _node(self, job, item, prefix, nodes):
        table, column = item.get(f"{prefix}_table", ""), item.get(f"{prefix}_column", "")
        component = item.get(f"{prefix}_component", "")
        if not column: return None
        node_id = self.asset_id(table or component, column, job)
        nodes.setdefault(node_id, {"id": node_id, "job_name": job, "table": table, "column": column,
                                  "component": component, "kind": prefix})
        return node_id

    @staticmethod
    def asset_id(table, column, job=""):
        return f"{job}:{table}.{column}".strip(".")

    @staticmethod
    def _add_cross_job(nodes, edges):
        producers, consumers = defaultdict(list), defaultdict(list)
        incoming = {e["target"] for e in edges}; outgoing = {e["source"] for e in edges}
        for node_id, node in nodes.items():
            key = (node.get("table", "").lower(), node.get("column", "").lower())
            if not all(key): continue
            if node_id in incoming: producers[key].append(node_id)
            if node_id in outgoing: consumers[key].append(node_id)
        for key in producers:
            for source in producers[key]:
                for target in consumers[key]:
                    if nodes[source]["job_name"] != nodes[target]["job_name"]:
                        edges.append({"source": source, "target": target, "type": "cross_job", "expression": "", "job_name": ""})

    @staticmethod
    def _dedupe(edges):
        seen, result = set(), []
        for edge in edges:
            key = (edge["source"], edge["target"], edge["type"])
            if key not in seen: seen.add(key); result.append(edge)
        return result

    @staticmethod
    def _adjacency(edges, reverse=False):
        result = defaultdict(list)
        for edge in edges:
            source, target = (edge["target"], edge["source"]) if reverse else (edge["source"], edge["target"])
            result[source].append(target)
        return {k: sorted(set(v)) for k, v in result.items()}

    @staticmethod
    def trace(graph, asset_id, downstream=True):
        adjacency = graph["adjacency" if downstream else "reverse_adjacency"]
        seen, pending = set(), deque([asset_id])
        while pending:
            node = pending.popleft()
            for other in adjacency.get(node, []):
                if other not in seen: seen.add(other); pending.append(other)
        return sorted(seen)
