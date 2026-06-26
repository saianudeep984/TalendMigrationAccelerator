"""
Enhanced Source & Target Extractor for Talend XML Parser
=========================================================
Extracts source and target tables/files/queries from parsed Talend
job component data.

The TalendJobParser stores all XML elementParameter values under
component["parameters"][<NAME>].  Simple attribute lookups like
c.get("table") return None — this module reads the nested dict.

Physical table resolution
-------------------------
``resolve_physical_table(component)`` returns a ``PhysicalTableRef``
dataclass populated from the component's parameter bag:

    database  ← DBNAME / DATABASE / CATALOG / context.xxx
    schema    ← SCHEMA_DB / SCHEMA / SCHEMANAME / DB_SCHEMA
    table     ← TABLE / TABLE_NAME / DBTABLE
    file_name ← FILE_NAME / FILENAME / FILE_PATH / OUTPUT_FILENAME / INPUT_FILENAME
    db_type   ← inferred from component type prefix or DB_VERSION / TYPE param

``build_component_physical_map(components)`` builds a
``dict[unique_name → PhysicalTableRef]`` for every source/target
component in a job, keyed by the component's UNIQUE_NAME.

``qualified_name`` on the returned dataclass is the resolved display
label, e.g. ``"MYSQL.CUSTOMERS"`` or ``"Oracle.HR.EMPLOYEES"`` —
replacing the raw component identifier (``tMysqlInput_1``) wherever
the lineage graph uses it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

try:
    import streamlit as st
except ImportError:
    import types as _types
    st = _types.SimpleNamespace(
        cache_data=lambda *a, **kw: (lambda fn: fn) if not a else a[0] if callable(a[0]) else (lambda fn: fn),
    )

# -------------------------------------------------------------------
# Component type classification
# -------------------------------------------------------------------

# Components whose primary role is reading data (sources)
_SOURCE_TYPES = {
    "tMysqlInput", "tOracleInput", "tMSSqlInput", "tPostgresqlInput",
    "tDB2Input", "tSybaseInput", "tInformixInput", "tTeradataInput",
    "tVerticaInput", "tSnowflakeInput", "tRedshiftInput",
    "tJDBCInput", "tGenericInput", "tELTInput",
    "tFileInputDelimited", "tFileInputExcel", "tFileInputJSON",
    "tFileInputXML", "tFileInputLDIF", "tFileInputRegex",
    "tFileInputFullRow", "tFileInputPositional",
    "tHiveInput", "tSparkInput", "tBigQueryInput",
    "tSalesforceInput", "tSAPInput", "tDynamicsInput",
    "tInputFileDelimited", "tRowGenerator",
    # catch-all: anything ending in Input
}

# Components whose primary role is writing data (targets)
_TARGET_TYPES = {
    "tMysqlOutput", "tOracleOutput", "tMSSqlOutput", "tPostgresqlOutput",
    "tDB2Output", "tSybaseOutput", "tInformixOutput", "tTeradataOutput",
    "tVerticaOutput", "tSnowflakeOutput", "tRedshiftOutput",
    "tJDBCOutput", "tGenericOutput", "tELTOutput",
    "tFileOutputDelimited", "tFileOutputExcel", "tFileOutputJSON",
    "tFileOutputXML", "tFileOutputLDIF",
    "tFileOutputFullRow", "tFileOutputPositional",
    "tHiveOutput", "tSparkOutput", "tBigQueryOutput",
    "tSalesforceOutput", "tSAPOutput", "tDynamicsOutput",
    "tOutputFileDelimited",
    # catch-all: anything ending in Output
}

# SQL-execution components (may be sources or targets depending on QUERY content)
_SQL_EXEC_TYPES = {
    "tMysqlRow", "tOracleRow", "tMSSqlRow", "tPostgresqlRow",
    "tJDBCRow", "tGenericRow", "tELTMap",
}

# db_type short-codes used in qualified_name prefix
_DB_TYPE_SHORTCODE: dict[str, str] = {
    "MySQL":            "MYSQL",
    "Oracle":           "ORACLE",
    "MS SQL Server":    "MSSQL",
    "PostgreSQL":       "POSTGRES",
    "IBM DB2":          "DB2",
    "Sybase":           "SYBASE",
    "Informix":         "INFORMIX",
    "Teradata":         "TERADATA",
    "Vertica":          "VERTICA",
    "Snowflake":        "SNOWFLAKE",
    "Amazon Redshift":  "REDSHIFT",
    "JDBC":             "JDBC",
    "Hive":             "HIVE",
    "Spark":            "SPARK",
    "BigQuery":         "BIGQUERY",
    "Salesforce":       "SALESFORCE",
    "SAP":              "SAP",
    "File":             "FILE",
    "Database":         "DB",
}

# -------------------------------------------------------------------
# PhysicalTableRef — the resolved physical identity of a component
# -------------------------------------------------------------------

@dataclass
class PhysicalTableRef:
    """
    Physical table/file coordinates resolved from a component's parameters.

    Attributes
    ----------
    unique_name   : str   Component UNIQUE_NAME  (e.g. "tMysqlInput_1")
    component_type: str   Talend component type  (e.g. "tMysqlInput")
    db_type       : str   Technology label       (e.g. "MySQL", "File")
    database      : str   Database/catalog name  (e.g. "customers_db")
    schema        : str   Schema/owner name      (e.g. "dbo", "HR")
    table         : str   Table name             (e.g. "CUSTOMERS")
    file_name     : str   File path/name         (e.g. "/data/export.csv")
    query_snippet : str   First 120 chars of SQL if no table name
    is_file       : bool  True when this is a file-based component
    is_resolved   : bool  True when at least one of table/file_name was found

    Derived
    -------
    qualified_name: str   Human-readable resolved label, e.g. "MYSQL.CUSTOMERS"
                          or "ORACLE.HR.EMPLOYEES" or "FILE:export.csv".
                          Falls back to component_type if nothing resolved.
    physical_key  : str   Normalised lowercase key for cross-job identity,
                          e.g. "mysql:customers_db.customers"
    """

    unique_name:    str = ""
    component_type: str = ""
    db_type:        str = ""
    database:       str = ""
    schema:         str = ""
    table:          str = ""
    file_name:      str = ""
    query_snippet:  str = ""
    is_file:        bool = False
    is_resolved:    bool = False

    @property
    def qualified_name(self) -> str:
        """
        Build the canonical display name for this component's physical target.

        Priority:
          1. File components  → ``FILE:<basename>``
          2. DB with schema   → ``<DB_TYPE>.<SCHEMA>.<TABLE>``
          3. DB with database → ``<DB_TYPE>.<DATABASE>.<TABLE>``
          4. DB table only    → ``<DB_TYPE>.<TABLE>``
          5. Query fallback   → ``<DB_TYPE>:SQL(…)``
          6. Unresolved       → component_type (original identifier)
        """
        prefix = _DB_TYPE_SHORTCODE.get(self.db_type, self.db_type.upper() if self.db_type else "")

        if self.is_file:
            fname = self.file_name.replace("\\", "/").split("/")[-1] if self.file_name else ""
            return f"FILE:{fname}" if fname else (prefix or "FILE")

        if self.table:
            if self.schema:
                return f"{prefix}.{self.schema.upper()}.{self.table.upper()}" if prefix else f"{self.schema.upper()}.{self.table.upper()}"
            if self.database:
                return f"{prefix}.{self.database.upper()}.{self.table.upper()}" if prefix else f"{self.database.upper()}.{self.table.upper()}"
            return f"{prefix}.{self.table.upper()}" if prefix else self.table.upper()

        if self.query_snippet:
            label = self.query_snippet[:60].strip()
            return f"{prefix}:SQL({label}…)" if prefix else f"SQL({label}…)"

        # Nothing resolved — return the original component identifier
        return self.unique_name or self.component_type

    @property
    def physical_key(self) -> str:
        """Normalised lowercase key for cross-job physical identity matching."""
        parts = [self.db_type.lower()] if self.db_type else []
        if self.database:
            parts.append(self.database.lower())
        if self.schema:
            parts.append(self.schema.lower())
        if self.table:
            parts.append(self.table.lower())
        elif self.file_name:
            parts.append(self.file_name.lower().replace("\\", "/").split("/")[-1])
        return ":".join(parts) if parts else ""


# -------------------------------------------------------------------
# Component type classification helpers
# -------------------------------------------------------------------

def _is_source(component_type: str) -> bool:
    return (
        component_type in _SOURCE_TYPES
        or component_type.endswith("Input")
    )


def _is_target(component_type: str) -> bool:
    return (
        component_type in _TARGET_TYPES
        or component_type.endswith("Output")
    )


def _is_sql_exec(component_type: str) -> bool:
    return component_type in _SQL_EXEC_TYPES or component_type.endswith("Row")


def _is_file_component(component_type: str) -> bool:
    """True when the component is file-based (not a DB component)."""
    ct = component_type.lower()
    return (
        "file" in ct
        or "excel" in ct
        or "csv" in ct
        or "ldif" in ct
        or "xml" in ct
        or "json" in ct
        or "regex" in ct
        or "positional" in ct
        or "fullrow" in ct
        or ct.startswith("tfileinput")
        or ct.startswith("tfileoutput")
        or ct in {"tinputfiledelimited", "toutputfiledelimited"}
    )


# -------------------------------------------------------------------
# Parameter extraction helpers
# -------------------------------------------------------------------

def _get_param(component: dict, *keys: str, default: str = "") -> str:
    """Return the first non-empty parameter value from a list of parameter keys."""
    params = component.get("parameters", {})
    for key in keys:
        val = params.get(key, "")
        if val and val not in ('""', "''", "null", "NULL", '""'):
            return val.strip('"').strip("'").strip()
    return default


def _strip_context(value: str) -> str:
    """
    Strip ``context.`` prefix from context variable references so we
    don't expose raw context variable names as physical identifiers.
    Returns empty string for pure context references (no static value).
    """
    if value.startswith("context."):
        return ""  # runtime value — can't resolve statically
    return value


def _db_type(component: dict) -> str:
    """Return the database / file type label for a component."""
    ct = component.get("component_type", "")

    # Explicit TYPE / DB_VERSION param wins
    for key in ("TYPE", "DB_VERSION", "DB_TYPE"):
        val = _get_param(component, key)
        if val:
            # Normalise DB_VERSION strings like "MYSQL_5" → "MySQL"
            val_clean = val.split("_")[0].capitalize()
            type_map = {
                "Mysql": "MySQL",
                "Oracle": "Oracle",
                "Mssql": "MS SQL Server",
                "Postgresql": "PostgreSQL",
                "Db2": "IBM DB2",
                "Sybase": "Sybase",
                "Informix": "Informix",
                "Teradata": "Teradata",
                "Vertica": "Vertica",
                "Snowflake": "Snowflake",
                "Redshift": "Amazon Redshift",
                "Jdbc": "JDBC",
                "Hive": "Hive",
                "Spark": "Spark",
                "Bigquery": "BigQuery",
            }
            mapped = type_map.get(val_clean)
            if mapped:
                return mapped

    # Infer from component name prefix
    prefix_map = {
        "tMysql":      "MySQL",
        "tOracle":     "Oracle",
        "tMSSql":      "MS SQL Server",
        "tPostgresql": "PostgreSQL",
        "tDB2":        "IBM DB2",
        "tSybase":     "Sybase",
        "tInformix":   "Informix",
        "tTeradata":   "Teradata",
        "tVertica":    "Vertica",
        "tSnowflake":  "Snowflake",
        "tRedshift":   "Amazon Redshift",
        "tJDBC":       "JDBC",
        "tHive":       "Hive",
        "tSpark":      "Spark",
        "tBigQuery":   "BigQuery",
        "tSalesforce": "Salesforce",
        "tSAP":        "SAP",
        "tFileInput":  "File",
        "tFileOutput": "File",
        "tInputFile":  "File",
        "tOutputFile": "File",
        "tIceberg":    "Iceberg",
    }
    for prefix, label in prefix_map.items():
        if ct.startswith(prefix):
            return label

    return "File" if _is_file_component(ct) else ("Database" if ("Input" in ct or "Output" in ct) else "")


# -------------------------------------------------------------------
# Physical table resolution — core implementation
# -------------------------------------------------------------------

def resolve_physical_table(component: dict) -> PhysicalTableRef:
    """
    Resolve the physical table/file coordinates for a single component.

    Reads the component's ``parameters`` dict (as produced by
    ``TalendJobParser.extract_components()``) and populates a
    ``PhysicalTableRef`` with whatever can be statically determined.

    Context variable references (e.g. ``context.database``) are
    silently dropped — they cannot be resolved without a runtime
    context.  The ``is_resolved`` flag on the returned ref indicates
    whether at least a table name or file path was found.

    Parameters
    ----------
    component : dict
        A component dict as returned by ``TalendJobParser.extract_components()``.
        Must contain ``"unique_name"``, ``"component_type"``, and
        ``"parameters"`` keys.

    Returns
    -------
    PhysicalTableRef
        Fully populated ref, with ``qualified_name`` and ``physical_key``
        computed lazily as properties.
    """
    ct = component.get("component_type", "")
    unique_name = component.get("unique_name", "")
    is_file = _is_file_component(ct)
    db_type_label = _db_type(component)

    # ── Database / catalog ────────────────────────────────────────────────────
    database = _strip_context(
        _get_param(component, "DBNAME", "DATABASE", "CATALOG", "DB_NAME", "SCHEMA_DB_IMPLICIT_CONTEXT")
    )

    # ── Schema / owner ────────────────────────────────────────────────────────
    schema = _strip_context(
        _get_param(component, "SCHEMA_DB", "SCHEMA", "SCHEMANAME", "SCHEMA_NAME", "DB_SCHEMA", "OWNER")
    )

    # ── Table name ────────────────────────────────────────────────────────────
    table = _strip_context(
        _get_param(component, "TABLE", "TABLE_NAME", "DBTABLE", "TABLENAME", "TABLE_FULL_NAME")
    )

    # ── File name ─────────────────────────────────────────────────────────────
    file_name = ""
    if is_file:
        file_name = _strip_context(
            _get_param(
                component,
                "FILE_NAME", "FILENAME", "FILE_PATH",
                "OUTPUT_FILENAME", "INPUT_FILENAME",
                "INPUTFILENAME", "OUTPUTFILENAME",
            )
        )

    # ── Query snippet (fallback when no table name) ───────────────────────────
    query_snippet = ""
    if not table and not file_name:
        raw_q = _get_param(component, "QUERY", "MEMO_SQL", "SQL_QUERY")
        if raw_q:
            # Collapse whitespace and trim
            query_snippet = re.sub(r"\s+", " ", raw_q).strip()[:120]

    is_resolved = bool(table or file_name or query_snippet)

    return PhysicalTableRef(
        unique_name=unique_name,
        component_type=ct,
        db_type=db_type_label,
        database=database,
        schema=schema,
        table=table,
        file_name=file_name,
        query_snippet=query_snippet,
        is_file=is_file,
        is_resolved=is_resolved,
    )


def build_component_physical_map(components: list[dict]) -> dict[str, "PhysicalTableRef"]:
    """
    Build a ``unique_name → PhysicalTableRef`` mapping for every
    source, target and SQL-execution component in a job.

    This is the primary entry point for the lineage graph builder:
    it passes the returned dict to ``build_graph()`` so every node
    whose label currently shows a raw component identifier (e.g.
    ``tMysqlInput_1``) can be replaced with the resolved qualified
    name (e.g. ``MYSQL.CUSTOMERS``).

    Components with an empty ``unique_name`` are silently skipped.

    Parameters
    ----------
    components : list[dict]
        As returned by ``TalendJobParser.extract_components()``.

    Returns
    -------
    dict[str, PhysicalTableRef]
        Keyed by component ``unique_name``.
    """
    result: dict[str, PhysicalTableRef] = {}
    for c in components:
        ct = c.get("component_type", "")
        uid = c.get("unique_name", "")
        if not uid:
            continue
        # Resolve for all source/target/SQL-exec components
        if _is_source(ct) or _is_target(ct) or _is_sql_exec(ct):
            result[uid] = resolve_physical_table(c)
    return result


# -------------------------------------------------------------------
# Legacy display helpers — unchanged public API
# -------------------------------------------------------------------

def _table_label(component: dict) -> str:
    """
    Return a human-readable table/file/query label for the component.
    Priority: TABLE > QUERY (first 80 chars) > FILE_NAME > UNIQUE_NAME.
    """
    table = _get_param(component, "TABLE", "TABLE_NAME", "DBTABLE")
    if table:
        return table

    query = _get_param(component, "QUERY", "MEMO_SQL")
    if query:
        short = query.replace("\n", " ").replace("\r", "")[:80].strip()
        return f"SQL: {short}{'...' if len(query) > 80 else ''}"

    fname = _get_param(
        component,
        "FILE_NAME", "FILENAME", "FILE_PATH",
        "OUTPUT_FILENAME", "INPUT_FILENAME",
    )
    if fname:
        return fname

    return _get_param(component, "UNIQUE_NAME") or component.get(
        "unique_name", component.get("component_type", "UNKNOWN")
    )


# -------------------------------------------------------------------
# Public API — source / target extraction (unchanged signatures)
# -------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def extract_sources(components: list[dict]) -> list[dict]:
    """
    Return a list of source descriptors extracted from parsed components.

    Each descriptor:
      {
        "name":           "<table / file / SQL snippet>",
        "type":           "<MySQL | Oracle | File | …>",
        "component":      "<tMysqlInput | …>",
        "unique_name":    "<UNIQUE_NAME>",
        "purpose":        "<human-readable purpose>",
        "physical_ref":   PhysicalTableRef,      # NEW — resolved coords
        "qualified_name": "<MYSQL.CUSTOMERS>",   # NEW — resolved display name
      }
    """
    results = []
    seen: set[str] = set()

    for c in components:
        ct = c.get("component_type", "")
        if not _is_source(ct):
            continue

        label = _table_label(c)
        if label in seen:
            continue
        seen.add(label)

        ref = resolve_physical_table(c)
        results.append({
            "name":           label,
            "type":           _db_type(c),
            "component":      ct,
            "unique_name":    c.get("unique_name", ""),
            "purpose":        f"Read data from {_db_type(c)} — {label}",
            "physical_ref":   ref,
            "qualified_name": ref.qualified_name,
        })

    return results


@st.cache_data(show_spinner=False)
def extract_source_systems(components: list[dict]) -> list[dict]:
    """
    Return a deduplicated list of distinct source SYSTEMS (e.g. MySQL,
    Oracle, File) feeding this job, aggregated across all source
    components.

    Each descriptor:
      {
        "system": "<MySQL | Oracle | File | …>",
        "count":  <number of source components of this system type>,
      }
    """
    counts: dict[str, int] = {}
    for c in components:
        ct = c.get("component_type", "")
        if not _is_source(ct):
            continue
        system = _db_type(c)
        counts[system] = counts.get(system, 0) + 1
    return [{"system": system, "count": count} for system, count in counts.items()]


@st.cache_data(show_spinner=False)
def extract_targets(components: list[dict]) -> list[dict]:
    """
    Return a list of target descriptors extracted from parsed components.

    Each descriptor:
      {
        "name":           "<table / file>",
        "type":           "<MySQL | Oracle | File | …>",
        "component":      "<tMysqlOutput | …>",
        "unique_name":    "<UNIQUE_NAME>",
        "purpose":        "<human-readable purpose>",
        "physical_ref":   PhysicalTableRef,      # NEW — resolved coords
        "qualified_name": "<MYSQL.CUSTOMERS>",   # NEW — resolved display name
      }
    """
    results = []
    seen: set[str] = set()

    for c in components:
        ct = c.get("component_type", "")
        if not _is_target(ct):
            continue

        label = _table_label(c)
        if label in seen:
            continue
        seen.add(label)

        ref = resolve_physical_table(c)
        results.append({
            "name":           label,
            "type":           _db_type(c),
            "component":      ct,
            "unique_name":    c.get("unique_name", ""),
            "purpose":        f"Write data to {_db_type(c)} — {label}",
            "physical_ref":   ref,
            "qualified_name": ref.qualified_name,
        })

    return results


@st.cache_data(show_spinner=False)
def extract_target_systems(components: list[dict]) -> list[dict]:
    """
    Return a deduplicated list of distinct target SYSTEMS written to
    by this job, aggregated across all target components.

    Each descriptor:
      {
        "system": "<MySQL | Oracle | File | …>",
        "count":  <number of target components of this system type>,
      }
    """
    counts: dict[str, int] = {}
    for c in components:
        ct = c.get("component_type", "")
        if not _is_target(ct):
            continue
        system = _db_type(c)
        counts[system] = counts.get(system, 0) + 1
    return [{"system": system, "count": count} for system, count in counts.items()]


@st.cache_data(show_spinner=False)
def extract_sql_operations(components: list[dict]) -> list[dict]:
    """
    Return SQL execution components (tMysqlRow, tJDBCRow, etc.)
    These may perform DELETE / UPDATE / INSERT directly.
    """
    results = []
    for c in components:
        ct = c.get("component_type", "")
        if not _is_sql_exec(ct):
            continue
        query = _get_param(c, "QUERY", "MEMO_SQL")
        ref = resolve_physical_table(c)
        results.append({
            "component":      ct,
            "unique_name":    c.get("unique_name", ""),
            "query":          query,
            "db_type":        _db_type(c),
            "physical_ref":   ref,
            "qualified_name": ref.qualified_name,
        })
    return results


def _component_query(component: dict) -> str:
    return _get_param(component, "QUERY", "MEMO_SQL", "SQL_QUERY")


def _sql_tables(pattern: str, sql: str) -> list[str]:
    results = set()
    for table in re.findall(pattern, str(sql or ""), flags=re.IGNORECASE):
        if not table or table.upper().startswith(("SELECT", "WHERE", "ON")):
            continue
        parts = table.strip('"[]`').split()
        if parts:
            results.add(parts[0])
    return sorted(results)


def _query_source_tables(sql_ops: list[dict]) -> list[dict]:
    results = []
    seen: set[str] = set()
    for op in sql_ops:
        query = op.get("query", "")
        tables = _sql_tables(r"\b(?:FROM|JOIN|USING)\s+([A-Za-z0-9_\.\[\]\"`]+)", query)
        for table in tables:
            if table in seen:
                continue
            seen.add(table)
            results.append({
                "name": table,
                "type": op.get("db_type", "SQL"),
                "component": op.get("component", "SQL"),
                "unique_name": op.get("unique_name", ""),
                "purpose": f"Read data from query table {table}",
                "physical_ref": op.get("physical_ref"),
                "qualified_name": table,
                "source": "query",
            })
    return results


def _query_source_tables_from_components(components: list[dict]) -> list[dict]:
    results = []
    seen: set[str] = set()
    for component in components:
        ct = component.get("component_type", "")
        if not (_is_source(ct) or _is_sql_exec(ct)):
            continue

        query = _component_query(component)
        if not query:
            continue

        tables = _sql_tables(r"\b(?:FROM|JOIN|USING)\s+([A-Za-z0-9_\.\[\]\"`]+)", query)
        ref = resolve_physical_table(component)
        for table in tables:
            if table in seen:
                continue
            seen.add(table)
            results.append({
                "name": table,
                "type": _db_type(component) or "SQL",
                "component": ct or "SQL",
                "unique_name": component.get("unique_name", ""),
                "purpose": f"Read data from query table {table}",
                "physical_ref": ref,
                "qualified_name": table,
                "source": "query",
            })
    return results


def _query_target_tables(sql_ops: list[dict]) -> list[dict]:
    results = []
    seen: set[str] = set()
    patterns = [
        r"\bINSERT\s+INTO\s+([A-Za-z0-9_\.\[\]\"`]+)",
        r"\bUPDATE\s+([A-Za-z0-9_\.\[\]\"`]+)",
        r"\bDELETE\s+FROM\s+([A-Za-z0-9_\.\[\]\"`]+)",
        r"\bMERGE\s+INTO\s+([A-Za-z0-9_\.\[\]\"`]+)",
        r"\bSELECT\b.+?\bINTO\s+([A-Za-z0-9_\.\[\]\"`]+)",
    ]
    for op in sql_ops:
        query = op.get("query", "")
        tables = []
        for pattern in patterns:
            tables.extend(_sql_tables(pattern, query))
        for table in tables:
            if table in seen:
                continue
            seen.add(table)
            results.append({
                "name": table,
                "type": op.get("db_type", "SQL"),
                "component": op.get("component", "SQL"),
                "unique_name": op.get("unique_name", ""),
                "purpose": f"Write data to query table {table}",
                "physical_ref": op.get("physical_ref"),
                "qualified_name": table,
                "source": "query",
            })
    return results


@st.cache_data(show_spinner=False)
def build_source_target_inventory(job_data: dict) -> dict:
    """
    Top-level helper that returns the full source/target inventory for a job.

    Returns:
      {
        "sources":        [ {name, type, component, purpose, physical_ref, qualified_name}, … ],
        "targets":        [ {name, type, component, purpose, physical_ref, qualified_name}, … ],
        "sql_operations": [ {component, query, db_type, physical_ref, qualified_name}, … ],
        "source_names":   ["table1", "table2", …],   # flat list for display
        "target_names":   ["tableA", …],
        "source_systems": [ {system, count}, … ],     # distinct source systems
        "target_systems": [ {system, count}, … ],     # distinct target systems
        "component_physical_map": { unique_name: PhysicalTableRef, … },  # NEW
      }
    """
    components = job_data.get("components", [])
    sql_ops    = extract_sql_operations(components)
    query_sources = _query_source_tables_from_components(components) or _query_source_tables(sql_ops)
    query_targets = _query_target_tables(sql_ops)
    sources    = query_sources or extract_sources(components)
    targets    = query_targets or extract_targets(components)
    source_systems = extract_source_systems(components)
    target_systems = extract_target_systems(components)
    comp_map   = build_component_physical_map(components)

    return {
        "sources":               sources,
        "targets":               targets,
        "sql_operations":        sql_ops,
        "source_names":          [s["name"] for s in sources] or ["(none detected)"],
        "target_names":          [t["name"] for t in targets] or ["(none detected)"],
        "source_systems":        source_systems,
        "target_systems":        target_systems,
        "component_physical_map": comp_map,
    }
