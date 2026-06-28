"""
Validates _render_tdd_download_section() for the Job 360 Analysis page's
"Documentation" and "Export Center" tabs (key_suffix="_j360_doc" and
"_j360_export_center" respectively — see app/ui/job_analysis_page.py).

Confirms:
  1. All 4 export formats (markdown, html, docx, pdf) generate without
     exception for both key_suffix contexts — including when both render
     in the *same* Streamlit script run, which is the worst case for
     widget-key collisions.
  2. The generated DOCX contains at least one embedded diagram image.
  3. The generated PDF contains the document title and section headings.
  4. No StreamlitDuplicateElementKey / DuplicateWidgetID errors occur.
"""
from __future__ import annotations

import os

from docx import Document
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

_KEY_SUFFIXES = ["_j360_doc", "_j360_export_center"]


def _job_data() -> dict:
    return {
        "job_name": "job_Orders_ETL",
        "components": [
            {"unique_name": "tFileInputDelimited_1", "component_type": "tFileInputDelimited"},
            {"unique_name": "tMap_1", "component_type": "tMap"},
            {"unique_name": "tFileOutputDelimited_1", "component_type": "tFileOutputDelimited"},
        ],
        "connections": [
            {"source": "tFileInputDelimited_1", "target": "tMap_1", "connector_type": "FLOW"},
            {"source": "tMap_1", "target": "tFileOutputDelimited_1", "connector_type": "FLOW"},
        ],
        "columns": [
            {"source": "id", "target": "id", "data_type": "Integer"},
            {"source": "name", "target": "name", "data_type": "String"},
        ],
        "schemas": [{"name": "main", "fields": [{"name": "id"}, {"name": "name"}]}],
        "column_mappings": [],
    }


def _app(key_suffixes: list, job_data: dict) -> None:
    """Renders _render_tdd_download_section once per key_suffix, in the same
    script run — the scenario that would surface duplicate widget keys."""
    import streamlit as st
    st.session_state["last_analysis_jobs"] = [{"job_data": job_data}]
    from app.ui.tdd_page import _render_tdd_download_section
    for suffix in key_suffixes:
        _render_tdd_download_section(_key_suffix=suffix)


def _render_and_generate() -> AppTest:
    """Renders both contexts side by side, then clicks 'Generate Exports'
    for each (default selection = all sections, all 4 formats)."""
    at = AppTest.from_function(_app, args=(_KEY_SUFFIXES, _job_data()))
    at.run(timeout=120)
    assert not at.exception, f"Initial render raised: {list(at.exception)}"

    for suffix in _KEY_SUFFIXES:
        at.button(key=f"tdd_generate_exports_btn{suffix}").click()
    at.run(timeout=120)
    return at


def test_all_four_formats_generate_without_exception():
    at = _render_and_generate()
    assert not at.exception, f"Export generation raised: {list(at.exception)}"
    assert not list(at.error), f"st.error fired during export: {[e.value for e in at.error]}"

    for suffix in _KEY_SUFFIXES:
        paths = at.session_state[f"tdd_export_paths{suffix}"]
        assert set(paths) == {"markdown", "html", "docx", "pdf"}, (
            f"{suffix}: expected all 4 formats, got {sorted(paths)}"
        )
        for fmt, path in paths.items():
            assert os.path.exists(path) and os.path.getsize(path) > 0, (
                f"{suffix}: {fmt} export missing or empty at {path}"
            )


def test_docx_contains_at_least_one_diagram():
    at = _render_and_generate()
    for suffix in _KEY_SUFFIXES:
        docx_path = at.session_state[f"tdd_export_paths{suffix}"]["docx"]
        doc = Document(docx_path)
        assert len(doc.inline_shapes) >= 1, f"{suffix}: DOCX has no embedded diagram images"


def test_pdf_contains_title_and_sections():
    at = _render_and_generate()
    for suffix in _KEY_SUFFIXES:
        pdf_path = at.session_state[f"tdd_export_paths{suffix}"]["pdf"]
        reader = PdfReader(pdf_path)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        assert "Technical Design Document" in text, f"{suffix}: PDF missing title"
        assert "Executive Summary" in text, f"{suffix}: PDF missing Executive Summary section"
        assert "Job Architecture" in text, f"{suffix}: PDF missing Job Architecture section"


def test_no_duplicate_element_key_errors():
    """Rendering both key_suffix contexts back-to-back in one script run is
    exactly the scenario that would surface a StreamlitDuplicateElementKey /
    DuplicateWidgetID error if any internal widget key were not namespaced
    by _key_suffix.
    """
    at = _render_and_generate()
    assert not at.exception, f"Duplicate-key error detected: {list(at.exception)}"

    # Negative control — confirms AppTest actually surfaces a real key
    # collision, so the absence of an exception above is meaningful and
    # not just a blind spot in the test harness.
    def _colliding_app():
        import streamlit as st
        st.download_button("A", data=b"a", file_name="a.txt", key="dup_key")
        st.download_button("B", data=b"b", file_name="b.txt", key="dup_key")

    control = AppTest.from_function(_colliding_app)
    control.run()
    assert control.exception, "Negative control did not raise — test methodology unsound"


def test_contexts_do_not_overwrite_each_others_exports_on_disk():
    """Regression test: the two contexts must not write their exports to the
    same path on disk, or one context's stored download can silently start
    serving the other context's content after both have generated.
    """
    at = AppTest.from_function(_app, args=(_KEY_SUFFIXES, _job_data()))
    at.run(timeout=120)

    # Context A ("_j360_doc"): only "Executive Summary" section, markdown only.
    for cb in at.checkbox:
        if cb.key.endswith("_j360_doc") and cb.key.startswith("tdd_sec_chk_"):
            cb.set_value("Executive Summary" in cb.label)
    at.multiselect(key="tdd_dl_fmt_sel_j360_doc").set_value(["📝 Markdown (.md)"])
    at.run(timeout=60)
    at.button(key="tdd_generate_exports_btn_j360_doc").click()
    at.run(timeout=120)
    path_a = at.session_state["tdd_export_paths_j360_doc"]["markdown"]
    with open(path_a, encoding="utf-8") as f:
        content_a = f.read()

    # Context B ("_j360_export_center"): default — all sections, all formats.
    at.button(key="tdd_generate_exports_btn_j360_export_center").click()
    at.run(timeout=120)

    with open(path_a, encoding="utf-8") as f:
        content_a_after_b = f.read()
    assert content_a_after_b == content_a, (
        "Context B's export overwrote Context A's file on disk — "
        "output paths are not isolated per _key_suffix"
    )
