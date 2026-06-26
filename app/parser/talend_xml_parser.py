from lxml import etree as ET
import json
import os


class TalendJobParser:

    def __init__(self, file_path):

        self.file_path = file_path

        self.root = None

        try:

            parser = ET.XMLParser(
                recover=True,
                encoding="utf-8"
            )

            self.tree = ET.parse(file_path, parser)

            self.root = self.tree.getroot()

        except Exception as e:

            print(f"Failed to parse XML: {file_path}")
            print(e)

            self.root = None

    # ---------------------------------------------------
    # Remove Namespace Helper
    # ---------------------------------------------------

    def strip_namespace(self, tag):

        if "}" in tag:
            return tag.split("}", 1)[1]

        return tag

    # ---------------------------------------------------
    # Find Elements by Local Tag Name
    # ---------------------------------------------------

    def find_elements(self, tag_name):

        results = []

        if self.root is None:
            return results

        for elem in self.root.iter():

            clean_tag = self.strip_namespace(elem.tag)

            if clean_tag == tag_name:
                results.append(elem)

        return results

    # ---------------------------------------------------
    # Extract Job Name
    # ---------------------------------------------------

    def get_job_name(self):
        import re
        file_name = os.path.basename(self.file_path)
        base = file_name.replace(".item", "")
        # Strip trailing version like _0.1, _0.2, _1.1 etc
        clean = re.sub(r'_\d+\.\d+$', '', base)
        return clean if clean else base

    def get_job_version(self):
        import re
        file_name = os.path.basename(self.file_path)
        base = file_name.replace(".item", "")
        m = re.search(r'_(\d+\.\d+)$', base)
        return m.group(1) if m else "0.1"

    def get_talend_version(self):
        """Detect Talend studio version from talend.project in the repo tree."""
        import re
        search_dir = os.path.dirname(self.file_path)
        # Walk upward up to 6 levels to find talend.project
        for _ in range(6):
            candidate = os.path.join(search_dir, "talend.project")
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    # productVersion="Talend Open Studio for Data Integration-6.0.1…"
                    m = re.search(r'productVersion=["\']([^"\']+)["\']', content)
                    if m:
                        raw = m.group(1)
                        # Extract the numeric version segment e.g. "6.0.1"
                        ver = re.search(r'(\d+\.\d+\.\d+)', raw)
                        return ver.group(1) if ver else raw
                except Exception:
                    pass
                return "Unknown"
            parent = os.path.dirname(search_dir)
            if parent == search_dir:
                break
            search_dir = parent
        # Fallback: infer from component versions in XML
        if self.root is not None:
            for elem in self.root.iter():
                tag = self.strip_namespace(elem.tag)
                if tag == "elementParameter" and elem.attrib.get("name") == "PRODUCT_VERSION":
                    v = elem.attrib.get("value", "")
                    if v:
                        return v
        return "Unknown"

    # ---------------------------------------------------
    # Extract Components
    # ---------------------------------------------------

    def extract_components(self):

        components = []

        nodes = self.find_elements("node")

        for node in nodes:

            component = {
                "unique_name": "",
                "component_type": "",
                "parameters": {}
            }

            component["component_type"] = node.attrib.get(
                "componentName",
                "UNKNOWN_COMPONENT"
            )

            for param in node.iter():

                clean_tag = self.strip_namespace(param.tag)

                if clean_tag != "elementParameter":
                    continue

                name = param.attrib.get("name")

                value = param.attrib.get("value")

                if name == "UNIQUE_NAME":
                    component["unique_name"] = value

                if name and value:
                    component["parameters"][name] = value

            # Lift key parameters to top-level for convenience
            params = component["parameters"]
            for lift_key in ("TABLE", "TABLE_NAME", "DBTABLE", "QUERY",
                             "MEMO_SQL", "FILE_NAME", "FILENAME",
                             "PROCESS", "DB_VERSION", "HOST", "DBNAME"):
                val = params.get(lift_key, "")
                if val:
                    component[lift_key.lower()] = val.strip('"').strip("'")
            components.append(component)

        return components

    # ---------------------------------------------------
    # Extract Connections
    # ---------------------------------------------------

    def extract_connections(self):

        connections = []

        conn_elements = self.find_elements("connection")

        for conn in conn_elements:

            connection = {
                "source": conn.attrib.get("source"),
                "target": conn.attrib.get("target"),
                "connector": conn.attrib.get("connectorName")
            }

            connections.append(connection)

        return connections

    # ---------------------------------------------------
    # Extract Context Variables
    # ---------------------------------------------------

    def extract_contexts(self):

        contexts = []

        context_elements = self.find_elements("context")

        for context in context_elements:

            context_data = {
                "name": context.attrib.get("name"),
                "value": context.attrib.get("value")
            }

            contexts.append(context_data)

        return contexts

    # ---------------------------------------------------
    # Validate Job
    # ---------------------------------------------------

    def is_valid_job(self):

        components = self.extract_components()

        return len(components) > 0

    # ---------------------------------------------------
    # Main Extraction
    # ---------------------------------------------------

    def extract_column_mappings(self):
        """Extract tMap column mappings: {Source Component, Source Column, Target Component, Target Column, Migration Rule}."""
        mappings = []
        if self.root is None:
            return mappings

        # Build connection index: label -> {source_component, target_component}
        conn_by_label = {}   # flow label -> {"source": compA, "target": compB}

        for elem in self.root.iter():
            tag = self.strip_namespace(elem.tag)
            if tag == "connection":
                label = elem.attrib.get("label", "").strip()
                src = elem.attrib.get("source", "").strip()
                tgt = elem.attrib.get("target", "").strip()
                connector = elem.attrib.get("connectorName", "").strip()
                if connector == "FLOW" and label:
                    conn_by_label[label] = {"source": src, "target": tgt}

        # Build input column type index per tMap: (tmap_uid, table_name, col_name) -> type
        input_col_types = {}  # (tmap_uid, table_name, col_name) -> talend_type

        def _derive_migration_rule(expression, target_type, nullable, operator,
                                   src_col, tgt_col, src_type):
            """Classify a single tMap output entry into a migration rule label."""
            import re as _re
            expr = expression.strip()

            # Join key: operator attribute present (=, !=, etc.)
            if operator:
                return "Join Key"

            # Context variable injection
            if expr.startswith("context."):
                return "Context Variable"

            # Pure direct-copy: expression is exactly "table.column" (optional trailing space)
            direct = _re.match(r'^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\s*$', expr)
            if direct:
                # Check for type change
                if src_type and target_type and src_type != target_type:
                    return "Type Cast"
                # Nullable change
                if nullable == "true" and src_type:
                    return "Direct Copy (Nullable)"
                return "Direct Copy"

            # Computed / expression: contains function call, arithmetic, concat, ternary
            has_func = bool(_re.search(r'[A-Za-z_][A-Za-z0-9_]*\s*\(', expr))
            has_arith = bool(_re.search(r'[\+\-\*\/]', expr))
            has_ternary = "?" in expr
            has_concat = '+"' in expr or '"+' in expr

            if has_ternary:
                return "Conditional Expression"
            if has_concat:
                return "String Concatenation"
            if has_func:
                return "Function Transform"
            if has_arith:
                return "Arithmetic Expression"

            # Multi-source reference (expression references a different table than src_col prefix)
            if "." in expr:
                ref_table = expr.split(".")[0].strip()
                src_table = src_col.split(".")[0].strip() if "." in src_col else ""
                if src_table and ref_table != src_table:
                    return "Cross-Table Reference"

            # Fallback
            return "Expression Mapping"

        # Find all tMap nodes and their input/output table → column mappings
        for node in self.root.iter():
            tag = self.strip_namespace(node.tag)
            if tag != "node":
                continue
            if node.attrib.get("componentName", "") != "tMap":
                continue

            # Get this tMap's unique name
            tmap_uid = ""
            for ep in node:
                etag = self.strip_namespace(ep.tag)
                if etag == "elementParameter" and ep.attrib.get("name") == "UNIQUE_NAME":
                    tmap_uid = ep.attrib.get("value", "").strip()

            # Default values per (table_name, col_name), from this node's <metadata> column lists
            default_by_table_col = {}
            for child in node:
                ctag = self.strip_namespace(child.tag)
                if ctag != "metadata":
                    continue
                meta_tbl = child.attrib.get("name", "").strip()
                for col_elem in child:
                    if self.strip_namespace(col_elem.tag) != "column":
                        continue
                    col_n = col_elem.attrib.get("name", "").strip()
                    dval = col_elem.attrib.get("defaultValue", "").strip()
                    if col_n:
                        default_by_table_col[(meta_tbl, col_n)] = dval

            # Parse nodeData for inputTables and outputTables with their entries
            input_tables = {}   # table_name -> [(col_name, talend_type)]
            output_tables = {}  # table_name -> [(target_col, expression, type, nullable, operator)]

            for child in node:
                ctag = self.strip_namespace(child.tag)
                if ctag != "nodeData":
                    continue
                for gchild in child:
                    gtag = self.strip_namespace(gchild.tag)
                    tbl_name = gchild.attrib.get("name", "").strip()
                    if gtag == "inputTables":
                        cols = []
                        for entry in gchild:
                            col = entry.attrib.get("name", "").strip()
                            typ = entry.attrib.get("type", "").strip()
                            if col:
                                cols.append((col, typ))
                                input_col_types[(tmap_uid, tbl_name, col)] = typ
                        input_tables[tbl_name] = cols
                    elif gtag == "outputTables":
                        entries = []
                        for entry in gchild:
                            col = entry.attrib.get("name", "").strip()
                            expr = entry.attrib.get("expression", "").strip()
                            typ = entry.attrib.get("type", "").strip()
                            nullable = entry.attrib.get("nullable", "").strip()
                            operator = entry.attrib.get("operator", "").strip()
                            if col:
                                entries.append((col, expr, typ, nullable, operator))
                        output_tables[tbl_name] = entries

            # Resolve source/target components via connections
            src_comp_by_table = {}
            tgt_comp_by_table = {}
            for label, conn in conn_by_label.items():
                if conn["target"] == tmap_uid:
                    src_comp_by_table[label] = conn["source"]
                if conn["source"] == tmap_uid:
                    tgt_comp_by_table[label] = conn["target"]

            # Build rows
            for out_tbl, entries in output_tables.items():
                tgt_comp = tgt_comp_by_table.get(out_tbl, out_tbl)
                for target_col, expression, tgt_type, nullable, operator in entries:
                    source_col = expression
                    src_comp = ""
                    src_type = ""
                    if "." in expression:
                        parts = expression.split(".", 1)
                        in_tbl = parts[0].strip()
                        raw_col = parts[1].strip()
                        src_comp = src_comp_by_table.get(in_tbl, in_tbl)
                        source_col = raw_col
                        src_type = input_col_types.get((tmap_uid, in_tbl, raw_col), "")

                    migration_rule = _derive_migration_rule(
                        expression, tgt_type, nullable, operator,
                        source_col, target_col, src_type
                    )

                    if src_type and tgt_type:
                        dtype_conv = "No Conversion" if src_type == tgt_type else f"{src_type} → {tgt_type}"
                    else:
                        dtype_conv = tgt_type or "—"

                    mappings.append({
                        "Source Component": src_comp or "—",
                        "Source Column": source_col,
                        "Target Component": tgt_comp or "—",
                        "Target Column": target_col,
                        "Migration Rule": migration_rule,
                        "Expression": expression,
                        "Data Type Conversion": dtype_conv,
                        "Default Value": default_by_table_col.get((out_tbl, target_col), "") or "—",
                    })

        return mappings

    def extract_mapping_rules(self):
        """Extract tMap lookup/join/filter rules from each tMap's inputTables
        (lookup + join config) and outputTables (nameless filter entries)."""
        rules = []
        if self.root is None:
            return rules

        # connection index: label -> {source, lineStyle}. Talend draws the
        # main tMap input as lineStyle "0" and lookup inputs as a dashed
        # line (non-"0"), so this distinguishes lookups from the main flow.
        conn_info_by_label = {}
        for elem in self.root.iter():
            if self.strip_namespace(elem.tag) == "connection" and \
               elem.attrib.get("connectorName", "") == "FLOW":
                label = elem.attrib.get("label", "").strip()
                if label:
                    conn_info_by_label[label] = {
                        "source": elem.attrib.get("source", "").strip(),
                        "lineStyle": elem.attrib.get("lineStyle", "0").strip(),
                    }

        for node in self.root.iter():
            if self.strip_namespace(node.tag) != "node":
                continue
            if node.attrib.get("componentName", "") != "tMap":
                continue
            tmap_uid = ""
            for ep in node:
                if self.strip_namespace(ep.tag) == "elementParameter" and ep.attrib.get("name") == "UNIQUE_NAME":
                    tmap_uid = ep.attrib.get("value", "").strip()

            for child in node:
                if self.strip_namespace(child.tag) != "nodeData":
                    continue
                for gchild in child:
                    gtag = self.strip_namespace(gchild.tag)
                    tbl_name = gchild.attrib.get("name", "").strip()

                    if gtag == "inputTables":
                        conn = conn_info_by_label.get(tbl_name, {})
                        is_lookup = conn.get("lineStyle", "0") != "0"
                        if not is_lookup:
                            continue  # main driving flow, not a lookup
                        inner_join = gchild.attrib.get("innerJoin", "").strip().lower() == "true"
                        rules.append({
                            "tMap": tmap_uid,
                            "Table": tbl_name,
                            "Lookup Source": conn.get("source", tbl_name) or tbl_name,
                            "Join Type": "Inner Join" if inner_join else "Left Outer Join",
                            "Match Mode": gchild.attrib.get("matchingMode", "").strip() or "—",
                            "Rule Type": "Lookup",
                        })

                    elif gtag == "outputTables":
                        for entry in gchild:
                            if self.strip_namespace(entry.tag) != "mapperTableEntries":
                                continue
                            if entry.attrib.get("name", "").strip():
                                continue  # column mapping, not a filter condition
                            expr = entry.attrib.get("expression", "").strip()
                            if expr:
                                rules.append({
                                    "tMap": tmap_uid,
                                    "Table": tbl_name,
                                    "Filter Expression": expr,
                                    "Rule Type": "Filter",
                                })

        # de-dup while preserving order
        seen, unique_rules = set(), []
        for r in rules:
            key = tuple(sorted(r.items()))
            if key not in seen:
                seen.add(key)
                unique_rules.append(r)
        return unique_rules

    def extract_job_info(self):

        if not self.is_valid_job():

            return {
                "job_name": "INVALID_JOB",
                "components": [],
                "connections": [],
                "contexts": []
            }

        return {
            "job_name": self.get_job_name(),
            "job_version": self.get_job_version(),
            "talend_version": self.get_talend_version(),
            "components": self.extract_components(),
            "connections": self.extract_connections(),
            "contexts": self.extract_contexts(),
            "column_mappings": self.extract_column_mappings(),
            "mapping_rules": self.extract_mapping_rules()
        }


# ---------------------------------------------------
# Standalone Execution
# ---------------------------------------------------

if __name__ == "__main__":

    sample_file = "sample_projects/sample.item"

    parser = TalendJobParser(sample_file)

    result = parser.extract_job_info()

    print(json.dumps(result, indent=4))