# TMA Testing Architecture

## Overview
Automated test generation layer built on top of `ai_test_generator.py`, `sql_assertion_generator.py`, and `test_case_generator.py`.

## Modules

### 1. Unit Tests (`generate_unit_tests`)
- Iterates every component in the job and generates an isolation test
- Falls back to `_fallback_test_cases` from `ai_test_generator` for category-level tests
- Covers: Source Validation, Target Validation, Row Count, Context, Error Handling, Performance, Regression

### 2. Validation SQL (`generate_validation_sql`)
Reuses `SQLAssertionGenerator.generate_for_table()`:
| Type | SQL Pattern |
|---|---|
| COUNT | `SELECT COUNT(*) FROM <table>` |
| MIN_MAX | Min/Max on primary key |
| HASH_VALIDATION | `SUM(ORA_HASH(ID))` |
| DUPLICATE_CHECK | GROUP BY key HAVING COUNT > 1 |
| NULL_CHECK | WHERE column IS NULL |
| SOURCE_COUNT | Pre-load baseline |
| NULL_KEY_CHECK | Source null PK guard |

### 3. Reconciliation Rules (`generate_reconciliation_rules`)
5 rules per source/target pair:
1. **Row Count Match** – Critical; zero tolerance
2. **Numeric Sum Match** – 0.1% tolerance on AMOUNT
3. **Date Range Integrity** – MIN/MAX date parity
4. **Orphan Record Check** – Anti-join both directions
5. **Hash Checksum** – `SUM(ORA_HASH(ID))` equality

### 4. Source vs Target Validation (`generate_src_vs_tgt`)
6 checks per pair:
1. Row Count
2. Column Nullability
3. Data Type Integrity
4. Aggregation Totals (variance < 0.1%)
5. Schema Column Parity (INFORMATION_SCHEMA)
6. Sample Row Comparison (first 100 rows)

## File Structure
```
app/
  tiap/testing/
    testing_architecture.py   ← New master module
    test_case_generator.py    ← Reused
    sql_assertion_generator.py← Reused
  ui/
    testing_architecture_page.py ← Streamlit UI with expandable sections
  generators/
    ai_test_generator.py      ← Reused (fallback + AI path)
docs/architecture/
  TMA_Testing_Architecture.md
```

## Integration
Add to `streamlit_app.py` / `streamlit_app_v2.py`:
```python
from app.ui.testing_architecture_page import render_testing_architecture_page
# In nav: render_testing_architecture_page(st.session_state.selected_job)
```
