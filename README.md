# Talend Migration Accelerator (TMA) — v11

AI-powered Talend Open Studio → Talend 8 migration platform and tooling.

This repository contains the Talend Migration Accelerator (TMA): analysis, assessment, and partial-automation tools to help migrate Talend Open Studio projects to Talend 8 / Talend Cloud. The primary UI is a Streamlit application located at `app/ui/streamlit_app.py`.

## Quick start

### Windows

Run the provided start script:

```
assets\start_accelerator.bat
```

### Linux / macOS

Create a virtual environment, install dependencies, and run the Streamlit UI:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/ui/streamlit_app.py
```

Open http://localhost:8501 in your browser.

Notes:
- The Streamlit entrypoint is `app/ui/streamlit_app.py`.
- A demo repository (expected path used by the UI: `data/demo_repository.zip`) can be loaded from the Upload tab if present.

---

## Main pages (top navigation)

The Streamlit UI uses a top navigation bar (Phase 1 UI refactor). Primary pages you will see:

- Migration Command Center (deep-dive analysis, dependency graphs, risks, AI insights)
- Version Converter (pre-flight analysis, mapping guidance)
- Executive Dashboard (KPIs and charts)
- Job Analysis / Job 360 (detailed per-job analysis and TDD / Docs Hub)
- Migration Assessment (cloud readiness, risks, effort estimation)
- Settings (assessment rules, AI / Ollama profiles, templates)

---

## Project layout (top-level)

```
app/                    Application modules: parsers, analyzers, ui, reports, engines
assets/                 Platform scripts (Windows start script)
cache/                  Runtime cache used during analysis
config/                 Configuration stores and default configs
docs/                   Documentation and design notes
output/                 Generated reports and exports (runtime)
sample_projects/        Example/samples used for development
scripts/                Utility scripts
tests/                  Test cases and harness
README.md               This file
requirements.txt        Python dependencies
run_tests.py            Test runner (project-specific harness)
```

How it fits together: streamlit_app imports analyzers, parsers, dependency graph builders and report generators from `app/` and orchestrates intake → analysis → review → export. Analysis runs in the backend (parsers and analyzers) and the UI renders the results and provides export/download actions.

---

## Running analysis

1. Upload a Talend export ZIP (File → Export Items → ZIP Archive) via the Upload tab.
2. Select the migration target (Talend 8, Talend Cloud, etc.) and (optionally) enable local Ollama LLM if available.
3. Click Analyze Repository — analysis typically takes 1–3 minutes depending on repository size.
4. Review results in Migration Review, use the Migration Assistant to guide fixes, and export reports/patches from the Generate / Download steps.

---

## Development & tests

- Python 3.9+
- See `requirements.txt` and `requirements-lock.txt` for dependencies.
- Run the project's test harness:

```
python run_tests.py
# or run pytest directly
pytest -q
```

---

## Notes & architecture highlights

- XML rewriting alone is insufficient — Talend Studio performs internal EMF graph reconstruction and repository synchronization during import. This tool provides analysis, partial transformations (patches) and recommendations, but the Talend Studio import step must complete the final migration.
- The UI underwent a Phase 1 refactor: sidebar navigation replaced with a top navigation bar; design system and compact page header are in `app/ui/design_system_v2.py` and used across pages.
- The Streamlit app references a local Ollama integration for optional LLM-powered analysis (see `app/config/ollama_profile_store.py` and the Settings → Ollama view).

---

## Where to look next (useful files)

- `app/ui/streamlit_app.py` — main Streamlit application
- `app/parser/` — Talend job discovery and parsing
- `app/analyzers/` — complexity, risk, cloud readiness, component analysis
- `app/dependency/` — dependency graph builder and exporter
- `app/reports/` — Excel and PDF export utilities
- `run_tests.py` — test harness used by the maintainers

---

If you'd like, I can further: update the README to include any specific developer setup steps (Docker, environment variables), add a minimal CONTRIBUTING.md, or open a PR with the README changes. Let me know which you prefer.