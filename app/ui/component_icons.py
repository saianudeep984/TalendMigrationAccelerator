"""Shared Talend component icon resolution for UI surfaces."""

from __future__ import annotations


DEFAULT_COMPONENT_ICON = "\u2699\ufe0f"

_ROLE_ICONS = {
    "source": "\U0001f4e5",
    "input": "\U0001f4e5",
    "transform": "\U0001f9e9",
    "validation": "\u2705",
    "target": "\U0001f4e4",
    "output": "\U0001f4e4",
    "arrow": "\u2192",
}

# Severity / risk-level icon used by Job 360 risk, warning and effort badges.
# Centralized here so individual pages never hardcode these as literal
# characters (mirrors the rule already applied to component_icon() below).
_SEVERITY_ICONS = {
    "CRITICAL": "\U0001f534",  # red circle
    "HIGH": "\U0001f7e0",      # orange circle
    "MEDIUM": "\U0001f7e1",    # yellow circle
    "LOW": "\U0001f7e2",       # green circle
}
DEFAULT_SEVERITY_ICON = "\u26aa"  # white circle — unknown/unrated severity


def severity_icon(level: str | None) -> str:
    """Return a stable icon for a HIGH/MEDIUM/LOW/CRITICAL severity label.

    Falls back to a neutral icon for any unrecognized value instead of
    ever rendering as an empty or broken placeholder.
    """
    key = str(level or "").strip().upper()
    return _SEVERITY_ICONS.get(key, DEFAULT_SEVERITY_ICON)


_EXACT_COMPONENT_ICONS = {
    "tMap": "\U0001f9e9",
    "tXMLMap": "\U0001f9e9",
    "tJoin": "\U0001f517",
    "tFilterRow": "\U0001f50e",
    "tAggregateRow": "\u03a3",
    "tSortRow": "\u2195\ufe0f",
    "tUniqueRow": "\U0001f194",
    "tNormalize": "\u22ee",
    "tDenormalize": "\u22ef",
    "tRunJob": "\u25b6\ufe0f",
    "tJoblet": "\U0001f9f1",
    "tJava": "\u2615",
    "tJavaRow": "\u2615",
    "tJavaFlex": "\u2615",
    "tBeanShell": "\u2615",
    "tLogRow": "\U0001f4cb",
    "tWarn": "\u26a0\ufe0f",
    "tDie": "\U0001f6d1",
    "tSendMail": "\u2709\ufe0f",
    "tGetMail": "\U0001f4e8",
}


def component_icon(component_type: str | None) -> str:
    """Return a stable icon for any Talend component type."""
    ctype = str(component_type or "").strip()
    if not ctype:
        return DEFAULT_COMPONENT_ICON
    if ctype in _EXACT_COMPONENT_ICONS:
        return _EXACT_COMPONENT_ICONS[ctype]

    c = ctype.lower()
    if "input" in c or c.endswith("get") or "read" in c:
        return "\U0001f4e5"
    if "output" in c or c.endswith("put") or "write" in c:
        return "\U0001f4e4"
    if any(token in c for token in ("db", "sql", "mysql", "oracle", "mssql", "postgres", "jdbc", "snowflake", "teradata", "redshift", "bigquery", "hive", "sybase")):
        return "\U0001f5c4\ufe0f"
    if any(token in c for token in ("file", "ftp", "sftp", "hdfs")):
        return "\U0001f4c1"
    if any(token in c for token in ("s3", "gcs", "azure", "dynamo", "cloud")):
        return "\u2601\ufe0f"
    if any(token in c for token in ("map", "json", "xml", "extract", "parse", "schema", "convert", "replace")):
        return "\U0001f9e9"
    if any(token in c for token in ("java", "groovy", "python", "ruby", "script", "beanshell")):
        return "\u2615"
    if any(token in c for token in ("runjob", "loop", "for", "parallel", "wait", "sleep", "prejob", "postjob")):
        return "\u25b6\ufe0f"
    if any(token in c for token in ("log", "catcher", "assert", "warn", "die", "stat", "meter")):
        return "\U0001f4cb"
    if any(token in c for token in ("rest", "http", "soap", "webservice", "salesforce")):
        return "\U0001f310"
    if any(token in c for token in ("kafka", "jms", "rabbit", "activemq", "mom")):
        return "\U0001f4e8"
    if "sap" in c:
        return "\U0001f3e2"
    if "context" in c or "global" in c:
        return "\U0001f527"
    return DEFAULT_COMPONENT_ICON

def component_role_icon(role: str | None) -> str:
    """Return an icon for generic component roles used by diagrams."""
    key = str(role or "").strip().lower()
    return _ROLE_ICONS.get(key, DEFAULT_COMPONENT_ICON)
