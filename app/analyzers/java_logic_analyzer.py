"""
Java Logic Analyzer
Discovers tJava/tJavaRow/tJavaFlex components, custom routines, and external JARs.
Produces: code viewer data, complexity scores, business rules, pseudocode,
           explanations, migration risk, and dependency graph data.
"""

import re

_JAVA_COMPONENT_TYPES = {"tJava", "tJavaRow", "tJavaFlex"}

# ── Risk patterns ─────────────────────────────────────────────────────────────
_PATTERNS = {
    "file_operations":    r"\b(File|FileInputStream|FileOutputStream|Files\.|BufferedReader|PrintWriter|FileReader|FileWriter)\b",
    "jdbc_calls":         r"\b(DriverManager|Connection|PreparedStatement|ResultSet|Statement)\b",
    "runtime_exec":       r"\b(Runtime\.getRuntime|ProcessBuilder|Class\.forName|ClassLoader)\b",
    "string_manip":       r"\b(StringBuilder|StringBuffer|substring|replaceAll|split\()\b",
    "loops":              r"\b(for|while)\s*\(",
    "conditionals":       r"\bif\s*\(",
    "error_handling":     r"\btry\s*\{|catch\s*\(",
    "system_env":         r"\bSystem\.(getenv|getProperty|setProperty)\b",
    "collections":        r"\b(List|Map|Set|ArrayList|HashMap|HashSet)\b",
    "math_ops":           r"\bMath\.\w+\(",
    "date_ops":           r"\b(Date|Calendar|LocalDate|DateFormat|SimpleDateFormat)\b",
    "external_jar":       r"\b(import\s+(?!java\.|javax\.)(?!org\.talend\.)[a-z][a-zA-Z0-9_]+\.[a-zA-Z0-9_.]+)",
}

_EXTERNAL_JAR_HINTS = [
    "org.apache.", "com.google.", "net.sf.", "io.spring.",
    "org.springframework.", "com.fasterxml.", "org.joda.", "org.bouncycastle.",
    "com.amazonaws.", "org.slf4j.", "ch.qos.", "org.json.", "com.opencsv.",
    "org.apache.poi", "org.apache.commons", "org.apache.http",
]


def _extract_component_code(comp: dict) -> str:
    """Pull Java code from component parameters."""
    params = comp.get("parameters") or {}
    code_keys = ("CODE", "EXPRESSION", "BODY", "PRECODE", "POSTCODE",
                 "JAVA_CODE", "EXPRESSION_CODE", "END_CODE", "START_CODE")
    parts = []
    for k in code_keys:
        v = params.get(k, "")
        if v:
            parts.append(str(v))
    # fall back to all param values if nothing found
    if not parts:
        for v in params.values():
            s = str(v or "")
            if len(s) > 20 and any(kw in s for kw in ("=", ";", "{", "}")):
                parts.append(s)
    return "\n".join(parts)


def _detect_flags(code: str) -> dict:
    return {k: bool(re.search(p, code)) for k, p in _PATTERNS.items()}


def _detect_external_jars(code: str) -> list[str]:
    jars = []
    for hint in _EXTERNAL_JAR_HINTS:
        if hint in code:
            jars.append(hint.rstrip("."))
    # Also catch explicit import statements for non-standard packages
    for m in re.finditer(r"import\s+((?!java\.|javax\.|org\.talend\.)[a-zA-Z][a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)\s*;", code):
        pkg = ".".join(m.group(1).split(".")[:3])
        if pkg not in jars:
            jars.append(pkg)
    return sorted(set(jars))


def _routine_references(code: str) -> list[str]:
    routines = []
    for rname in re.findall(r"\b([A-Z][A-Za-z0-9_]+)\s*\.", str(code or "")):
        if rname not in {"String", "System", "Math", "Date", "Calendar", "LocalDate"}:
            routines.append(rname)
    return sorted(set(routines))


def _complexity_score(flags: dict, loc: int) -> dict:
    """Return a numeric complexity score and label."""
    score = 0
    if flags.get("runtime_exec"):
        score += 30
    if flags.get("file_operations"):
        score += 20
    if flags.get("jdbc_calls"):
        score += 15
    if flags.get("system_env"):
        score += 10
    if flags.get("loops"):
        score += 10
    if flags.get("conditionals"):
        score += 5
    if flags.get("error_handling"):
        score += 5
    if flags.get("string_manip"):
        score += 5
    if flags.get("date_ops"):
        score += 5
    if flags.get("collections"):
        score += 5
    score += min(20, loc // 10)  # up to 20 pts for code volume

    if score >= 70:
        label = "CRITICAL"
    elif score >= 45:
        label = "HIGH"
    elif score >= 20:
        label = "MEDIUM"
    else:
        label = "LOW"
    return {"score": min(score, 100), "label": label}


def _migration_risk(flags: dict, ext_jars: list, complexity: dict) -> dict:
    risks = []
    if flags.get("runtime_exec"):
        risks.append({"risk": "CRITICAL", "reason": "Uses Runtime.exec / ProcessBuilder — blocked in cloud environments."})
    if flags.get("file_operations"):
        risks.append({"risk": "HIGH", "reason": "Local file I/O; target environment may not support direct FS access."})
    if flags.get("system_env"):
        risks.append({"risk": "HIGH", "reason": "Reads/writes system environment/properties — unreliable in containers."})
    if flags.get("jdbc_calls"):
        risks.append({"risk": "MEDIUM", "reason": "Direct JDBC calls; replace with Talend DB components for portability."})
    if ext_jars:
        risks.append({"risk": "MEDIUM", "reason": f"External JARs detected ({', '.join(ext_jars[:3])}); must be bundled in target env."})
    if not risks:
        risks.append({"risk": "LOW", "reason": "No critical cloud-incompatible patterns detected."})
    overall = max(risks, key=lambda r: {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}[r["risk"]])
    return {"overall": overall["risk"], "findings": risks}


def _recommendations(flags: dict, ext_jars: list, routines: list[str], ctype: str) -> list[dict]:
    recs = []
    if ctype == "tJavaFlex":
        recs.append({
            "priority": "HIGH",
            "category": "Component Modernization",
            "recommendation": "Refactor tJavaFlex logic into tJavaRow, tMap, or reusable routines before migration.",
        })
    if flags.get("runtime_exec"):
        recs.append({
            "priority": "CRITICAL",
            "category": "Cloud Compatibility",
            "recommendation": "Replace Runtime.exec / ProcessBuilder with managed orchestration, APIs, or platform-native tasks.",
        })
    if flags.get("file_operations"):
        recs.append({
            "priority": "HIGH",
            "category": "File Handling",
            "recommendation": "Move local file I/O to supported storage connectors or externalized landing zones.",
        })
    if flags.get("jdbc_calls"):
        recs.append({
            "priority": "MEDIUM",
            "category": "Database Access",
            "recommendation": "Replace direct JDBC code with Talend database components where practical.",
        })
    if flags.get("system_env"):
        recs.append({
            "priority": "MEDIUM",
            "category": "Configuration",
            "recommendation": "Move system properties and environment reads into Talend contexts or deployment variables.",
        })
    if ext_jars:
        recs.append({
            "priority": "MEDIUM",
            "category": "External Libraries",
            "recommendation": "Validate library versions, licenses, and packaging for the target runtime.",
        })
    if routines:
        recs.append({
            "priority": "MEDIUM",
            "category": "Routines",
            "recommendation": "Review shared routines for Java version compatibility, side effects, and reusable test coverage.",
        })
    if not recs:
        recs.append({
            "priority": "LOW",
            "category": "Validation",
            "recommendation": "Retain the Java logic but add regression tests around input/output behavior.",
        })
    return recs


def _business_rules(flags: dict, code: str) -> list[str]:
    rules = []
    if flags.get("conditionals"):
        conds = re.findall(r"if\s*\((.{0,80})\)", code)
        for c in conds[:5]:
            rules.append(f"Conditional logic: {c.strip()}")
    if flags.get("loops"):
        rules.append("Iterative processing loop detected — likely row-by-row or batch transformation.")
    if flags.get("jdbc_calls"):
        rules.append("Custom JDBC database operation — direct query execution in Java code.")
    if flags.get("file_operations"):
        rules.append("File I/O operation — reads or writes to local file system.")
    if flags.get("string_manip"):
        rules.append("String transformation logic — custom text processing or formatting.")
    if flags.get("date_ops"):
        rules.append("Date/time manipulation — custom date parsing or formatting.")
    if flags.get("math_ops"):
        rules.append("Mathematical computation — numeric calculation or aggregation.")
    return rules or ["No explicit business rules detected in this code block."]


def _pseudocode(flags: dict, ctype: str, code: str) -> str:
    lines = [f"// [{ctype}] Pseudocode summary"]
    if flags.get("file_operations"):
        lines.append("OPEN file from local path")
        lines.append("READ / WRITE file content")
    if flags.get("jdbc_calls"):
        lines.append("CONNECT to database via JDBC")
        lines.append("EXECUTE SQL query")
        lines.append("PROCESS result set rows")
    if flags.get("loops"):
        lines.append("FOR each row / item in dataset:")
    if flags.get("conditionals"):
        lines.append("  IF condition is met:")
        lines.append("    APPLY transformation logic")
        lines.append("  ELSE:")
        lines.append("    HANDLE default case")
    if flags.get("string_manip"):
        lines.append("TRANSFORM string values (split / replace / format)")
    if flags.get("date_ops"):
        lines.append("PARSE or FORMAT date/time values")
    if flags.get("math_ops"):
        lines.append("CALCULATE numeric result")
    if flags.get("error_handling"):
        lines.append("TRY: execute main logic")
        lines.append("CATCH exception: log error / fail job")
    if flags.get("runtime_exec"):
        lines.append("EXECUTE external OS command or process")
    if flags.get("system_env"):
        lines.append("READ system environment variable or JVM property")
    if len(lines) == 1:
        lines.append("EXECUTE custom Java logic (no patterns auto-detected)")
    return "\n".join(lines)


def _explanation(flags: dict, ctype: str, ext_jars: list, loc: int) -> str:
    parts = [f"This **{ctype}** component contains {loc} line(s) of custom Java code."]
    features = []
    if flags.get("file_operations"):
        features.append("local file I/O")
    if flags.get("jdbc_calls"):
        features.append("direct JDBC database calls")
    if flags.get("runtime_exec"):
        features.append("OS process execution")
    if flags.get("string_manip"):
        features.append("string manipulation")
    if flags.get("date_ops"):
        features.append("date/time handling")
    if flags.get("math_ops"):
        features.append("mathematical operations")
    if features:
        parts.append(f"It performs: {', '.join(features)}.")
    if ext_jars:
        parts.append(f"External libraries referenced: {', '.join(ext_jars)}.")
    if flags.get("error_handling"):
        parts.append("Error handling is present (try/catch).")
    return " ".join(parts)


def _ai_explanation(job_name: str, components: list[dict], routines: dict[str, int], jars: list[str], risk: str) -> str:
    if not components and not routines and not jars:
        return f"{job_name} has no detected inline Java, routine usage, or external Java libraries."

    comp_types = sorted({c["component_type"] for c in components})
    parts = [
        f"{job_name} contains {len(components)} inline Java component(s)"
        + (f" ({', '.join(comp_types)})" if comp_types else "")
        + f" with overall {risk} migration risk."
    ]
    if routines:
        parts.append(
            "It references shared routines such as "
            + ", ".join(f"{name} ({count}x)" for name, count in sorted(routines.items(), key=lambda x: -x[1])[:5])
            + ", so routine compatibility should be validated once for all consuming jobs."
        )
    if jars:
        parts.append(
            "It depends on external Java libraries "
            + ", ".join(jars[:5])
            + ", which must be available and version-compatible in the target runtime."
        )
    top_findings = []
    for comp in components:
        top_findings.extend(f["reason"] for f in comp.get("risk", {}).get("findings", []) if f.get("risk") != "LOW")
    if top_findings:
        parts.append("Primary concerns: " + " ".join(dict.fromkeys(top_findings[:3])))
    return " ".join(parts)


def analyze_java_logic(job: dict) -> dict:
    """
    Full Java logic analysis for a single job.
    Returns a dict with component-level detail and job-level summaries.
    """
    jd = job.get("job_data", {})
    job_name = jd.get("job_name", "Unknown")

    java_comps = [
        c for c in jd.get("components", [])
        if c.get("component_type") in _JAVA_COMPONENT_TYPES
    ]

    # ── Routine discovery from component params ────────────────────────────────
    routine_usage: dict[str, int] = {}
    for c in jd.get("components", []):
        for v in (c.get("parameters") or {}).values():
            for rname in _routine_references(str(v)):
                routine_usage[rname] = routine_usage.get(rname, 0) + 1

    # ── Per-component analysis ─────────────────────────────────────────────────
    components = []
    all_ext_jars: list[str] = []
    dep_nodes: list[str] = []
    dep_edges: list[tuple[str, str]] = []

    for c in java_comps:
        ctype = c.get("component_type", "tJava")
        uid = c.get("unique_name", ctype)
        code = _extract_component_code(c)
        loc = len([l for l in code.splitlines() if l.strip()])
        flags = _detect_flags(code)
        ext_jars = _detect_external_jars(code)
        routines = _routine_references(code)
        all_ext_jars.extend(ext_jars)
        complexity = _complexity_score(flags, loc)
        risk = _migration_risk(flags, ext_jars, complexity)
        rules = _business_rules(flags, code)
        pseudo = _pseudocode(flags, ctype, code)
        explanation = _explanation(flags, ctype, ext_jars, loc)
        recs = _recommendations(flags, ext_jars, routines, ctype)

        dep_nodes.append(uid)
        if flags.get("jdbc_calls"):
            dep_edges.append((uid, "DB (JDBC)"))
            dep_nodes.append("DB (JDBC)")
        if flags.get("file_operations"):
            dep_edges.append((uid, "File System"))
            dep_nodes.append("File System")
        for jar in ext_jars:
            dep_edges.append((uid, jar))
            dep_nodes.append(jar)

        components.append({
            "uid": uid,
            "component_type": ctype,
            "code": code,
            "loc": loc,
            "flags": flags,
            "external_jars": ext_jars,
            "routines": routines,
            "complexity": complexity,
            "risk": risk,
            "business_rules": rules,
            "pseudocode": pseudo,
            "explanation": explanation,
            "ai_explanation": explanation,
            "recommendations": recs,
        })

    # ── Job-level roll-up ─────────────────────────────────────────────────────
    all_ext_jars_unique = sorted(set(all_ext_jars))
    total_loc = sum(c["loc"] for c in components)
    max_complexity = max((c["complexity"]["score"] for c in components), default=0)
    max_risk = max(
        (c["risk"]["overall"] for c in components),
        key=lambda r: {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}.get(r, 0),
        default="LOW",
    )

    # Dependency graph data (for mermaid)
    graph_nodes = list(dict.fromkeys(dep_nodes))  # preserve order, deduplicate
    graph_edges = list(dict.fromkeys(dep_edges))
    inventory = [
        {
            "Component": c["uid"],
            "Type": c["component_type"],
            "LOC": c["loc"],
            "Complexity": c["complexity"]["label"],
            "Complexity Score": c["complexity"]["score"],
            "Risk": c["risk"]["overall"],
            "Routines": ", ".join(c.get("routines", [])),
            "External Libraries": ", ".join(c.get("external_jars", [])),
        }
        for c in components
    ]
    recommendations = []
    for comp in components:
        for rec in comp.get("recommendations", []):
            recommendations.append({"Component": comp["uid"], **rec})
    if routine_usage and not any(r["category"] == "Routines" for r in recommendations):
        recommendations.append({
            "Component": "Shared routines",
            "priority": "MEDIUM",
            "category": "Routines",
            "recommendation": "Review referenced routines for Java version compatibility and shared regression coverage.",
        })
    if all_ext_jars_unique and not any(r["category"] == "External Libraries" for r in recommendations):
        recommendations.append({
            "Component": "External libraries",
            "priority": "MEDIUM",
            "category": "External Libraries",
            "recommendation": "Validate library packaging, licenses, and runtime compatibility.",
        })

    return {
        "job_name": job_name,
        "java_component_count": len(java_comps),
        "components": components,
        "java_inventory": inventory,
        "routine_usage": routine_usage,
        "external_jars": all_ext_jars_unique,
        "total_loc": total_loc,
        "max_complexity_score": max_complexity,
        "overall_risk": max_risk,
        "ai_explanation": _ai_explanation(job_name, components, routine_usage, all_ext_jars_unique, max_risk),
        "recommendations": recommendations,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
    }
