# TMA AI Executive Summary

## Overview
Per-job, AI-assisted executive summary layer producing five capped sections (max 10 lines each): Business Summary, Technical Summary, Risks, Opportunities, Recommendations.

## Modules

### 1. Business Summary (`generate_business_summary`)
CIO-style plain-English summary of the job's purpose. Uses Ollama when reachable; otherwise a dedicated rule-based fallback (not the shared generic `llm_engine` fallback, which is tuned for migration-recommendation prompts and would not differentiate business vs technical intent).

### 2. Technical Summary (`generate_technical_summary`)
Architect-style summary covering component count and types. Same Ollama/fallback pattern as Business Summary, with its own dedicated fallback text.

### 3. Risks (`generate_risks`)
Reuses `app.tiap.migration_assessment.build_migration_assessment` — no risk logic duplicated. Capped at 10 lines.

### 4. Opportunities (`generate_opportunities`)
Grounded in migration assessment's unsupported-components and cloud-readiness output; falls back deterministically when Ollama is unavailable.

### 5. Recommendations (`generate_recommendations`)
Reuses migration assessment's `recommendations` list directly, capped at 10 lines.

## File Structure
```
app/
  tiap/exec_summary/
    exec_summary.py        ← New master module
  ui/
    exec_summary_page.py   ← Streamlit UI, expandable sections
docs/architecture/
  TMA_AI_Executive_Summary.md
```

## Integration
Wired into `streamlit_app.py` nav (`_sel == "exec_summary"`) and `_NAV_PAGES` in `design_system_v2.py`.
