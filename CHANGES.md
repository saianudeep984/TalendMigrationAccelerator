# TMA Documentation Hub UX Redesign + Complete Visual Export — Changes

This release delivers two parallel improvements:

1. **Documentation Hub UI redesign** — modern enterprise UX with document
   cards, professional tabs, sticky bottom toolbar and a polished Export
   Center.
2. **Complete visual export framework** — every chart, image, lineage
   graph, architecture diagram and Mermaid flowchart shown in TMA is now
   embedded into the corresponding PDF / HTML / DOCX / ZIP exports.

This release is **fully additive** on top of the previous Stability + Export
Center release. No existing generators, schemas, routes or APIs were
modified.

---

## 1. Documentation Hub UI redesign

* New hero header — gradient banner, repo-relevant subtitle.
* **Document Navigation Cards** (7 cards) above the main content:
  TDD · LLD · Runbook · Architecture · Executive · Migration · Validation.
  Each card shows icon, title, description, status pill (Ready / Pending),
  and an estimated page count. The active card is visually highlighted.
* **Tab bar** built on `st.segmented_control` (radio replacement) for
  document selection — falls back to `st.radio` on older Streamlit.
* **Left sidebar navigator** preserved (already collapsible via Streamlit).
* **Sticky bottom toolbar** with Previous / Next / Export controls.
* **Export Center redesign** — 6 explicit sections (Mode · Documents ·
  Sections · Format · Preview · Generate), gradient hero, custom summary
  cards, and a five-card visual preview row showing detected
  Images / Charts / Diagrams / Lineage / Assets size before export.
* All styling injected via per-page `<style>` blocks; no global CSS
  conflicts with the existing `apply_wizard_theme()`.
* Files: `app/ui/documentation_hub_page.py`, `app/ui/export_center.py`.

## 2. Export asset framework

New module `app/ui/export_assets.py` builds a per-document `AssetManifest`
of PNG/SVG/JPEG/GIF visuals every time an export runs:

* `plotly_to_png(fig)` — Plotly → PNG via Kaleido (legends, labels,
  colours preserved).
* `matplotlib_to_png(fig)` — Matplotlib → PNG (Agg backend, headless).
* `networkx_to_png(graph)` — NetworkX → PNG via Matplotlib spring layout
  with node + edge labels.
* `dot_to_png(dot)` — Graphviz DOT → PNG via the `dot` binary.
* `mermaid_to_png(code)` — Mermaid → DOT (using the existing
  `mermaid_to_dot` helper) → PNG.
* `scan_disk_assets("output")` — picks up any image already produced by
  other parts of TMA and classifies it as image / chart / diagram.
* `chart_kpis / chart_complexity / chart_readiness` — synthesises
  Executive KPI bar, Complexity-distribution pie and Readiness RAG bar
  (Matplotlib).
* `diagram_lineage(jobs)` and `diagram_architecture(jobs)` — synthesises
  data-lineage (NetworkX) and architecture-overview (Graphviz) diagrams.
* `collect_for_doc(doc_type)` — returns a manifest for any of the seven
  supported document types, blending generated visuals with disk-scanned
  assets.

Asset embedding uses a single `asset:KEY` markdown placeholder so every
format-specific writer can resolve it natively.

## 3. Visual export enhancements

New module `app/ui/export_writers.py` replaces the writer chain in the
Export Center:

* **HTML** — single-file portable HTML; images base64-embedded under
  `<figure><img/><figcaption/></figure>`. CSS preserves typography,
  cover page, TOC and section break styles.
* **PDF** — reportlab-driven multi-page PDF that:
  * Embeds the `Image` flowable for every `asset:KEY` reference.
  * Auto-scales oversized images to fit page width.
  * Renders Markdown tables to `Table`/`TableStyle` (zebra stripes,
    repeating header).
  * Adds cover page + Table of Contents.
* **DOCX** — `python-docx`-driven document; `add_picture(BytesIO, width=6")`
  for every asset reference; section ordering preserved; captions kept as
  italic 9 pt paragraphs.
* **ZIP package** — new layout exactly matching the spec:
  ```
  Documentation_Package/
  ├── Index.html
  ├── Assets/         (union of every visual asset)
  ├── Images/
  ├── Charts/
  ├── Diagrams/
  ├── TDD/            (TDD.pdf · TDD.html · TDD.docx)
  ├── LLD/
  ├── Runbook/
  ├── Executive/
  ├── Architecture/
  ├── Migration/
  └── Validation/
  ```
  `Index.html` now includes a per-document card grid (PDF / HTML / DOCX
  links) and a 12-tile visual gallery referencing `Assets/`.
* The Export Center's "Preview" row counts every visual a manifest will
  embed (Images / Charts / Diagrams / Lineage / size) so users can verify
  before generating.

## 4. Validation results

`tests/test_export_center.py` was extended; running it locally now
yields:

```
[OK] action_panel import
[OK] safe_get for ExecutiveDashboard + dict
[OK] sanitize_dataframe_for_streamlit
[OK] use_container_width replaced
[OK] chart_kpis (15763 bytes)
[OK] chart_complexity (27903 bytes)
[OK] Executive Report: 3 assets {'chart': 3}
[OK] TDD: 5 assets {'chart': 1, 'lineage': 1, 'diagram': 3}
[OK] LLD: 5 assets {'chart': 1, 'lineage': 1, 'diagram': 3}
[OK] Architecture Report: 5 assets {'diagram': 4, 'lineage': 1}
[OK] Migration Runbook: 1 assets {'chart': 1}
[OK] Validation Report: 1 assets {'chart': 1}
[OK] Migration Report: 2 assets {'chart': 2}
[OK] Executive PDF: Executive_Report.pdf (83 KB)
[OK] TDD HTML embeds images (<img>, <figure>)
[OK] Architecture DOCX embeds 2 images (word/media/imageN.png)
[OK] Selected sections export
[OK] Multiple PDF / HTML / DOCX / ZIP
[OK] Complete Documentation Package — 64 entries, Charts/ + Diagrams/
     + Assets/ all populated with PNGs
[OK] Documentation Hub redesign — 7 doc cards, sticky toolbar, tabs

[PASS] All Phase 1 fixes, Phase 2 Export Center with visuals, and UX
       redesign verified.
```

## Dependencies added

`requirements.txt` was extended with:

* `matplotlib>=3.6.0,<4.0.0` — chart synthesis + NetworkX rendering.
* `kaleido>=0.2.1` — Plotly → PNG.

`graphviz` (already pinned) is now used at runtime via the system
`dot` binary for Mermaid / DOT → PNG conversion.
