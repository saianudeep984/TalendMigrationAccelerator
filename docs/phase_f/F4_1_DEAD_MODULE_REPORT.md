# F4.1 Dead-Module Report — Readiness Modules

Scanner: `app.readiness.dependency_mapper.build_dependency_map()` (app/-tree
import scan) + repo-wide `tests/`/`scripts/` text/AST cross-check.

## Orphans found (zero importers) — DELETED in F4.2

| Module | Path | Notes |
|---|---|---|
| app.migration_assistant.migration_readiness | app/migration_assistant/migration_readiness.py | `class MigrationReadiness`, no importers anywhere |
| app.readiness.cloud_blockers | app/readiness/cloud_blockers.py | no imports, no content references |
| app.readiness.talend8_readiness | app/readiness/talend8_readiness.py | `class Talend8Readiness`; superseded by `app.analyzers.readiness_scorer.Talend8Readiness` |
| app.tiap.assessment.migration_readiness | app/tiap/assessment/migration_readiness.py | `class MigrationReadinessAnalyzer`, no importers |

## Exempted false-positive

| Module | Reason |
|---|---|
| app.tiap.assessment.cloud_readiness | Zero importers inside `app/` after deletions above, but imported directly by `tests/test_cloud_readiness_canonical_engine.py` as a tested backward-compat alias of `app.analyzers.cloud_readiness.CloudReadinessAnalyzer`. Kept. |

## Post-deletion verification (F4.3)

- AST syntax check: 0 errors across repo.
- Full `app/` package import: 308/308 modules import cleanly.
- `READINESS_MODULES` registry in `dependency_mapper.py` updated to drop the 4 deleted entries.
- `tests/test_readiness_dependency_mapper.py` updated to assert post-deletion state.
- Full test suite: 181/181 passed.
