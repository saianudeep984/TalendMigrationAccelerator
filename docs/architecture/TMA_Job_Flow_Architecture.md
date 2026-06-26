# TMA Job Flow Architecture — Update_mean_max

## End-to-End Flow
```
Update_mean_max (orchestrator)
 └─ tMysqlRow_1 (DELETE precheck)
     └─[OnSubjobOk]→ tRunJob_1 → Plugin_Max_values (full subjob)
         └─[OnSubjobOk]→ tRunJob_3 → GA_Max_values (full subjob)
```
Both subjobs execute the identical 13-component ETL chain; GA_Max_values runs only after Plugin_Max_values completes OK.

## Component Sequence (per subjob: Plugin_Max_values / GA_Max_values)
1. tMysqlRow_1 — DELETE precheck on `mean_values`
2. tMysqlInput_1 — KPI source query (pivoted AVG/STDDEV)
3. tMap_1 — reshape, splits to two branches
4. tUnpivotRow_1 (Mean branch) / tUnpivotRow_2 (Max branch) — parallel
5. tMap_2 (Mean) / tMap_4 or tMap_5 (Max) — parallel
6. tAggregateRow_1 (Mean branch only) → tMap_3 (lookup join)
   tMysqlOutput_2 (Max branch) → tLogRow_2
7. tMysqlInput_2 — lookup source, feeds tMap_3
8. tMysqlOutput_1 — writes enriched rows
9. tLogRow_1 — logs write count

## Trigger Links
| Source | Target | Link Type | Trigger |
|---|---|---|---|
| tMysqlRow_1 (orchestrator) | tRunJob_1 | SUBJOB_OK | OnSubjobOk |
| tRunJob_1 | tRunJob_3 | SUBJOB_OK | OnSubjobOk |
| tMysqlRow_1 (subjob) | tMysqlInput_1 | SUBJOB_OK | OnSubjobOk |
| all remaining links | — | FLOW | row/data links |

## Subjobs
- **Update_mean_max_0.1** — orchestrator; 1 subjob (tMysqlRow_1 → tRunJob_1 → tRunJob_3, all OnSubjobOk chained)
- **Plugin_Max_values_1.0** — called subjob; 1 internal subjob (tMysqlRow_1 OnSubjobOk → tMysqlInput_1, then full FLOW chain)
- **GA_Max_values_1.0** — called subjob; identical structure to Plugin_Max_values

## Execution Order
1. Update_mean_max: tMysqlRow_1 (cleanup DELETE)
2. Plugin_Max_values invoked (tRunJob_1) — runs steps below to completion
   2a. tMysqlRow_1 → 2b. tMysqlInput_1 → 2c. tMap_1 → 2d. (tUnpivotRow_1 ‖ tUnpivotRow_2) → 2e. (tMap_2 ‖ tMap_5) → 2f. tAggregateRow_1 ‖ tMysqlOutput_2→tLogRow_2 → 2g. tMysqlInput_2 (lookup) → 2h. tMap_3 → 2i. tMysqlOutput_1 → 2j. tLogRow_1
3. GA_Max_values invoked (tRunJob_3) — same sequence as step 2, using tMap_4 in place of tMap_5
