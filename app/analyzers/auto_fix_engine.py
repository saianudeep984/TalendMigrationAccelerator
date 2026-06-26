"""
Auto-Fix Recommendation Engine
Produces per-job actionable fix list.
"""

try:
    import streamlit as st
except ImportError:
    import types as _types
    st = _types.SimpleNamespace(
        cache_data=lambda *a, **kw: (lambda fn: fn) if not a else a[0] if callable(a[0]) else (lambda fn: fn),
    )
from app.config.component_rules import (
    DEPRECATED_COMPONENT_MAP,
    AUTO_FIX_RULES,
    TALEND8_KNOWN_COMPONENTS,
    COMPONENT_RISK_RULES,
)


@st.cache_data(show_spinner=False)
def generate_auto_fix_recommendations(_all_jobs):
    """
    Returns list of fix items per job:
        { job_name, issue, impact, risk, fix, auto_fix, effort }
    """

    recommendations = []

    for job in _all_jobs:
        job_name = job["job_data"]["job_name"]
        seen = set()

        for comp in job["job_data"]["components"]:
            ctype = comp["component_type"]
            if ctype in seen:
                continue
            seen.add(ctype)

            # Deprecated fix
            if ctype in DEPRECATED_COMPONENT_MAP:
                rule = DEPRECATED_COMPONENT_MAP[ctype]
                recommendations.append({
                    "job_name": job_name,
                    "issue": f"{ctype} is deprecated",
                    "impact": f"Replace with {rule['replacement']}",
                    "risk": rule["risk"],
                    "fix": AUTO_FIX_RULES.get(ctype, f"Replace with {rule['replacement']}"),
                    "auto_fix": rule["auto_fix"],
                    "effort": "Low" if rule["auto_fix"] else "Medium"
                })

            # Custom / unknown
            elif ctype not in TALEND8_KNOWN_COMPONENTS:
                recommendations.append({
                    "job_name": job_name,
                    "issue": f"{ctype} is a custom/unknown component",
                    "impact": "Not available in Talend 8 catalog",
                    "risk": "HIGH",
                    "fix": "Manual implementation or vendor-supplied T8 version required",
                    "auto_fix": False,
                    "effort": "High"
                })

            # Risk rule
            elif ctype in COMPONENT_RISK_RULES:
                rule = COMPONENT_RISK_RULES[ctype]
                if rule["risk"] in ("HIGH", "CRITICAL"):
                    recommendations.append({
                        "job_name": job_name,
                        "issue": rule["issue"],
                        "impact": rule["recommendation"],
                        "risk": rule["risk"],
                        "fix": rule["recommendation"],
                        "auto_fix": False,
                        "effort": "High" if rule["risk"] == "CRITICAL" else "Medium"
                    })

    return recommendations
