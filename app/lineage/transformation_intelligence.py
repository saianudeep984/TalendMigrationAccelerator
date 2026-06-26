"""Transformation extraction and chain visualization."""
from dataclasses import asdict, is_dataclass


def _dict(value):
    return asdict(value) if is_dataclass(value) else dict(value) if isinstance(value, dict) else vars(value)


class TransformationIntelligence:
    def extract(self, mappings=None, rules=None, components=None, job_name=""):
        rows = []
        for mapping in mappings or []:
            item = _dict(mapping); expression = item.get("expression", "") or ""
            rule = (item.get("rule_type") or item.get("rule") or "mapping").lower()
            kind = "aggregation" if "aggregate" in rule or any(x in expression.lower() for x in (".sum(", ".count(", ".max(", ".min(")) else "expression" if expression else "mapping"
            rows.append({"job_name": job_name, "type": kind, "source": self._asset(item, "source"),
                         "target": self._asset(item, "target"), "expression": expression,
                         "component": item.get("source_component", item.get("component", ""))})
        for rule in rules or []:
            item = _dict(rule); text = " ".join(str(v) for v in item.values()).lower()
            kind = "join" if item.get("join_type") or "join" in text else "lookup" if "lookup" in text else "filter" if item.get("filter_expression") or "filter" in text else "expression"
            rows.append({"job_name": job_name, "type": kind, "table": item.get("table", ""),
                         "expression": item.get("filter_expression", ""), "details": item})
        for component in components or []:
            ctype = component.get("component_type", "") if isinstance(component, dict) else str(component)
            kind = "aggregation" if ctype in {"tAggregateRow", "tAggregateSortedRow"} else "filter" if ctype in {"tFilterRow", "tFilterColumns"} else "join" if ctype in {"tJoin", "tMap", "tXMLMap"} else "lookup" if "Lookup" in ctype else None
            if kind: rows.append({"job_name": job_name, "type": kind, "component": component.get("unique_name", ctype), "component_type": ctype})
        counts = {kind: sum(r["type"] == kind for r in rows) for kind in ("join", "lookup", "filter", "expression", "aggregation", "mapping")}
        return {"transformations": rows, "counts": counts, "chains": self._chains(rows), "visualization": self.visualize(rows)}

    analyze = extract

    @staticmethod
    def _asset(item, prefix):
        table, column = item.get(f"{prefix}_table", ""), item.get(f"{prefix}_column", "")
        return ".".join(x for x in (table, column) if x)

    @staticmethod
    def _chains(rows):
        return [{"source": r.get("source", ""), "transformation": r["type"], "target": r.get("target", ""), "expression": r.get("expression", "")} for r in rows if r.get("source") or r.get("target")]

    @staticmethod
    def visualize(rows):
        lines = ["flowchart LR"]
        for index, row in enumerate(rows):
            if row.get("source") and row.get("target"):
                source = f"S{index}"; tx = f"X{index}"; target = f"T{index}"
                lines += [f'    {source}["{row["source"]}"] --> {tx}["{row["type"]}"]', f'    {tx} --> {target}["{row["target"]}"]']
        return "\n".join(lines)
