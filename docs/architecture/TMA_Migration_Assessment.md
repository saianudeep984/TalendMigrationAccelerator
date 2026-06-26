# TMA Migration Assessment

## Overview
Per-job migration assessment layer built on top of existing analyzers: `calculate_cloud_readiness`, `analyze_unsupported_components`, `RiskAnalyzer`, and `ComplexityAnalyzer`.

## Modules

### 1. Cloud Readiness (`get_cloud_readiness`)
Reuses `app.analyzers.cloud_readiness.calculate_cloud_readiness`. Returns `readiness` (HIGH/MEDIUM/LOW), `rag` status, and Java task risk findings — no remediation logic duplicated.

### 2. Unsupported Components (`get_unsupported_components`)
Wraps the single job and reuses `app.analyzers.unsupported_component_analyzer.analyze_unsupported_components`. Reports category, instance count, jobs impacted, and impact level:
| Category | Impact |
|---|---|
| tJava* | HIGH |
| tSystem | CRITICAL |
| Custom Routines | MEDIUM |
| Custom JDBC | HIGH |

### 3. Migration Risks (`get_migration_risks`)
Reuses `app.risk_engine.risk_analyzer.RiskAnalyzer`. Each risk is classified into a 3-tier bucket (High / Medium / Low) for display, with CRITICAL folded into High.

### 4. Effort Estimation (`get_effort_estimation`)
Derives hours and complexity from `ComplexityAnalyzer` (single-job wrap), surfacing effort drivers (component count, structural complexity, unsupported component remediation).

### 5. Recommendations (`get_recommendations`)
Synthesized from the above: cloud blocker remediation, per-category unsupported-component fixes, and high-risk component remediation guidance.

## File Structure
```
app/
  tiap/migration_assessment/
    migration_assessment.py     ← New master module
  ui/
    migration_assessment_page.py ← Streamlit UI with expandable sections
docs/architecture/
  TMA_Migration_Assessment.md
```

## Integration
Wired into `streamlit_app.py` nav (`_sel == "migration_assessment"`) and `_NAV_PAGES` in `design_system_v2.py`.
