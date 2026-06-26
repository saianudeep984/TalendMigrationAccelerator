"""
TMA Documentation Export Center — automated validation.

Verifies Phase 1 stability fixes, Phase 2 export modes, the new
visual-export framework (Phase 2 of the second pass), and the
Documentation Hub UX redesign (Phase 1 of the second pass).

Exits 0 on success, 1 on any failure.

    python tests/test_export_center.py
"""
from __future__ import annotations

import io
import os
import sys
import traceback
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def _seed_state() -> None:
    import streamlit as st
    st.session_state.clear()
    st.session_state["last_analysis_jobs"] = [
        {
            "job_data": {
                "job_name": f"job_{i}",
                "components": [
                    {"name": "tFileInputDelimited", "type": "tFileInputDelimited"},
                    {"name": "tMap_1", "type": "tMap"},
                    {"name": "tFileOutputDelimited", "type": "tFileOutputDelimited"},
                ],
                "columns": [
                    {"source": "id",   "target": "id",   "data_type": "Integer"},
                    {"source": "name", "target": "name", "data_type": "String"},
                ],
                "schemas": [{"name": "main", "fields": [{"name": "id"}, {"name": "name"}]}],
            }
        }
        for i in range(5)
    ]
    st.session_state["last_repo_name"] = "ValidationRepo"
    st.session_state["readiness_score"] = {"overall": "GREEN", "auto_score": 80}
    st.session_state["effort_estimate"] = {
        "auto_pct": 80, "manual_pct": 20, "estimated_hours": 400,
        "estimated_weeks": 10, "estimated_days": 50,
        "by_complexity": {"LOW": 3, "MEDIUM": 1, "HIGH": 1},
    }
    st.session_state["routine_analysis"] = {"total_routines": 0}
    st.session_state["joblet_analysis"] = {"total_joblets": 0}
    st.session_state["deprecated_rows"] = []
    st.session_state["custom_analysis"] = {}
    st.session_state["migration_runbook"] = {
        "summary": "Sample runbook",
        "pre_checklist": ["Backup", "Notify stakeholders"],
        "cutover": ["Stop sources", "Run migration", "Validate"],
        "rollback": ["Restore backup"],
        "validation": ["Row count", "Checksum"],
    }
    st.session_state["architecture_autofix_intelligence"] = {
        "summary": "Sample architecture",
        "auto_fix_recommendations": [
            {"title": "Replace tHashOutput", "description": "Use tFileOutputDelimited", "priority": "HIGH"}
        ],
    }
    st.session_state["migration_intelligence"] = {"summary": "MI sample"}
    st.session_state["impact_intelligence"] = {"summary": "II sample"}


def _check(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def main() -> int:
    failures: list[str] = []

    # ── Phase 1 stability fixes ──────────────────────────────────────────
    try:
        from app.ui.design_system_v2 import action_panel  # noqa: F401
        print("[OK] action_panel import")
    except Exception as e:
        failures.append(f"action_panel import failed: {e}")

    try:
        from app.utils.safe_access import safe_get, sanitize_dataframe_for_streamlit
        from app.analyzers.models import ExecutiveDashboard
        ed = ExecutiveDashboard(total_jobs=42, total_components=99)
        _check(safe_get(ed, "total_jobs") == 42, "safe_get attribute lookup failed")
        _check(safe_get({"totalJobs": 7}, "total_jobs") == 7, "safe_get camel→snake fallback failed")
        print("[OK] safe_get for ExecutiveDashboard + dict")

        import pandas as pd
        df = pd.DataFrame([{"a": 1, "b": {"k": "v"}, "c": [1, 2]}, {"a": 2, "b": None, "c": {1, 2}}])
        sdf = sanitize_dataframe_for_streamlit(df)
        _check("dict" not in str(type(sdf.iloc[0]["b"])), "dict cell not coerced")
        print("[OK] sanitize_dataframe_for_streamlit")
    except Exception as e:
        failures.append(f"Phase 1 helpers failed: {e}\n{traceback.format_exc()}")

    bad: list[str] = []
    for root, _dirs, files in os.walk(os.path.join(ROOT, "app")):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8") as fh:
                if "use_container_width" in fh.read():
                    bad.append(p)
    if bad:
        failures.append(f"use_container_width still present in: {bad}")
    else:
        print("[OK] use_container_width replaced")

    # ── Visual asset framework ──────────────────────────────────────────
    _seed_state()
    try:
        from app.ui.export_assets import (
            collect_for_doc, plotly_to_png, matplotlib_to_png,
            networkx_to_png, mermaid_to_png, dot_to_png,
            chart_kpis, chart_complexity, chart_readiness,
            diagram_lineage, diagram_architecture,
        )
        # Renderers smoke-test.
        kpi = chart_kpis({"A": 10, "B": 20})
        _check(kpi is not None and len(kpi.data) > 100, "chart_kpis failed")
        print(f"[OK] chart_kpis ({len(kpi.data)} bytes)")

        cmp = chart_complexity({"LOW": 3, "MEDIUM": 2, "HIGH": 1})
        _check(cmp is not None and len(cmp.data) > 100, "chart_complexity failed")
        print(f"[OK] chart_complexity ({len(cmp.data)} bytes)")

        # Per-doc collection.
        for d in ["Executive Report", "TDD", "LLD", "Architecture Report",
                  "Migration Runbook", "Validation Report", "Migration Report"]:
            m = collect_for_doc(d)
            _check(len(m.assets) >= 1, f"{d} produced no assets")
            print(f"[OK] {d}: {len(m.assets)} assets {m.counts}")
    except Exception as e:
        failures.append(f"Visual asset framework failed: {e}\n{traceback.format_exc()}")

    # ── Phase 2: Export Center with visuals embedded ────────────────────
    try:
        from app.ui.export_center import (
            export_single, export_multiple, export_complete_package,
            FORMAT_PDF, FORMAT_HTML, FORMAT_DOCX, FORMAT_ZIP,
            DOC_TDD, DOC_LLD, DOC_RUNBOOK, DOC_EXEC, DOC_ARCH, DOC_VALID, DOC_MIGRATION,
            ALL_DOCUMENTS,
        )

        # Single doc — every format must include images for visual-rich docs.
        data, fname, mime = export_single(DOC_EXEC, FORMAT_PDF)
        _check(len(data) > 5000, "Executive PDF too small to contain visuals")
        print(f"[OK] Executive PDF: {fname} ({len(data)} bytes)")

        data, fname, mime = export_single(DOC_TDD, FORMAT_HTML)
        _check(b"<img" in data, "TDD HTML missing <img>")
        _check(b"<figure>" in data, "TDD HTML missing <figure>")
        print(f"[OK] TDD HTML embeds images")

        data, fname, mime = export_single(DOC_ARCH, FORMAT_DOCX)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            media = [n for n in zf.namelist() if "word/media/" in n]
            _check(len(media) >= 1, "Architecture DOCX has no embedded images")
        print(f"[OK] Architecture DOCX embeds {len(media)} images")

        # Section filter.
        data, fname, mime = export_single(DOC_TDD, FORMAT_HTML, only_sections=["Executive Summary"])
        _check(b"Executive Summary" in data, "section filter did not include selected section")
        print(f"[OK] Selected sections export")

        # Multi.
        for fmt in [FORMAT_PDF, FORMAT_HTML, FORMAT_DOCX, FORMAT_ZIP]:
            data, fname, mime = export_multiple([DOC_TDD, DOC_EXEC], fmt)
            _check(len(data) > 0, f"multi {fmt} empty")
            print(f"[OK] Multiple {fmt}: {len(data)} bytes")

        # Complete package.
        data, fname, mime = export_complete_package()
        _check(fname == "Documentation_Package.zip", "package filename wrong")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            _check(any("Index.html" in n for n in names), "package missing Index.html")
            _check(any("/Assets/" in n and n.endswith(".png") for n in names),
                   "package Assets/ has no PNGs")
            _check(any("/Charts/" in n and n.endswith(".png") for n in names),
                   "package Charts/ has no PNGs")
            _check(any("/Diagrams/" in n and n.endswith(".png") for n in names),
                   "package Diagrams/ has no PNGs")
            for d in ALL_DOCUMENTS:
                folder = {
                    DOC_TDD: "TDD", DOC_LLD: "LLD", DOC_RUNBOOK: "Runbook",
                    DOC_EXEC: "Executive", DOC_ARCH: "Architecture",
                    DOC_VALID: "Validation", DOC_MIGRATION: "Migration",
                }[d]
                _check(any(folder + "/" in n for n in names), f"package missing {folder}/ folder")
        print(f"[OK] Complete Documentation Package: {fname} ({len(data)} bytes, {len(names)} entries)")
    except Exception as e:
        failures.append(f"Phase 2 Export Center failed: {e}\n{traceback.format_exc()}")

    # ── Phase 1 (this pass): UX redesign hooks ───────────────────────────
    try:
        from app.ui.documentation_hub_page import (
            _DOC_CARDS, _render_doc_navigation_cards, _render_doc_tabs,
            _render_sticky_toolbar, render_documentation_hub_page,
        )
        _check(len(_DOC_CARDS) == 7, "Expected 7 doc cards")
        print(f"[OK] Documentation Hub redesign — {len(_DOC_CARDS)} doc cards, sticky toolbar, tabs")
    except Exception as e:
        failures.append(f"UX redesign hooks failed: {e}\n{traceback.format_exc()}")

    print()
    if failures:
        print(f"[FAIL] {len(failures)} validation failure(s):")
        for fmsg in failures:
            print(f"  - {fmsg}")
        return 1
    print("[PASS] All Phase 1 fixes, Phase 2 Export Center with visuals, and UX redesign verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
