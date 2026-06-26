"""Column and table business-criticality scoring."""
from collections import defaultdict


class BusinessCriticalityScorer:
    def score(self, lineage):
        nodes = lineage.get("nodes", []); edges = lineage.get("edges", [])
        incoming, outgoing = defaultdict(int), defaultdict(int)
        for edge in edges: outgoing[edge["source"]] += 1; incoming[edge["target"]] += 1
        tx_count = defaultdict(int)
        for tx in lineage.get("transformations", []):
            if tx.get("source"): tx_count[tx["source"]] += 1
            if tx.get("target"): tx_count[tx["target"]] += 1
        columns = []
        for node in nodes:
            node_id = node["id"]; frequency = incoming[node_id] + outgoing[node_id]
            downstream = self._downstream(lineage.get("adjacency", {}), node_id)
            asset = ".".join(x for x in (node.get("table", ""), node.get("column", "")) if x)
            transformation_complexity = tx_count[node_id] + tx_count[asset]
            score = min(100, frequency * 10 + (incoming[node_id] + outgoing[node_id]) * 8 + len(downstream) * 6 + transformation_complexity * 12)
            columns.append({"asset_id": node_id, "table": node.get("table", ""), "column": node.get("column", ""),
                            "score": score, "criticality": self.classify(score), "usage_frequency": frequency,
                            "dependency_count": incoming[node_id] + outgoing[node_id], "downstream_impact": len(downstream),
                            "transformation_complexity": transformation_complexity})
        tables = defaultdict(list)
        for row in columns:
            if row["table"]: tables[row["table"]].append(row["score"])
        table_rows = [{"table": table, "score": round(max(scores) * .7 + sum(scores) / len(scores) * .3),
                       "criticality": self.classify(round(max(scores) * .7 + sum(scores) / len(scores) * .3))}
                      for table, scores in tables.items()]
        return {"columns": sorted(columns, key=lambda x: -x["score"]), "tables": sorted(table_rows, key=lambda x: -x["score"]),
                "critical_assets": [x for x in columns if x["criticality"] in {"CRITICAL", "HIGH"}]}

    analyze = score

    @staticmethod
    def _downstream(adjacency, start):
        seen, pending = set(), [start]
        while pending:
            for node in adjacency.get(pending.pop(), []):
                if node not in seen: seen.add(node); pending.append(node)
        return seen

    @staticmethod
    def classify(score):
        return "CRITICAL" if score >= 75 else "HIGH" if score >= 50 else "MEDIUM" if score >= 25 else "LOW"
