# TMA Validation Architecture — Update_mean_max
Detected via direct XML inspection (no `tFilterRow`, `tSchemaComplianceCheck`, `tUniqRow`, or `REJECT` connectors exist in this project — all validation is implicit, embedded in SQL, schema flags, and component settings).

## Null Checks
| Location | Mechanism |
|---|---|
| tMysqlInput_1 (all 3 jobs) | SQL `IF(P1=0,1,P1)` zero/null-safe division guards before ratio KPI calcs (Mean Page Views per Visit, Avg Visit Duration, Visitor Loyalty) |
| Schema-level | 33–61 columns per job marked `nullable="false"` on key business fields (companyid, paramid, datasetgroup) |
| tAggregateRow_1 | `IGNORE_NULL` flag per operation: `true` on mean_value/max_value aggregates, `false` on companyid/datasetgroup/Process_Date (FIRST function must not silently skip nulls on identity columns) |

## Data Quality Rules
| Rule | Where |
|---|---|
| Rounding precision | `ROUND(..., 2)` enforced on all 20 KPI pairs in tMysqlInput_1 — prevents floating-point drift |
| Type enforcement | Schema casts: VARCHAR→id_String, DOUBLE→id_Double, INT→id_Integer, DATETIME→id_Date(`dd-MM-yyyy`) |
| DIE_ON_ERROR | `true` on all tMap_1–tMap_4 nodes (job aborts on transform error); `false` on tMysqlOutput_1/_2 and tMysqlRow_1 (write/delete errors don't hard-stop) |

## Duplicate Checks
| Mechanism | Detail |
|---|---|
| Lookup match mode | tMap_3 lookup join to config table uses `UNIQUE_MATCH` (Inner Join) — rejects rows with multiple matching lookup keys, enforcing 1:1 cardinality |
| Write action | tMysqlOutput_1 uses `UPDATE` action (upsert on PK) — duplicate companyid/paramid rows overwrite rather than duplicate |
| No explicit tUniqRow | No dedicated dedup component; reliance is entirely on lookup match mode + UPDATE semantics |

## Schema Validation
| Check | Detail |
|---|---|
| Primary/key flags | 9 `key="true"` columns in GA_Max_values/Plugin_Max_values (id, companyid, paramid identity columns across metadata blocks) |
| Length/precision constraints | Explicit `length`/`precision` per column (e.g. companyid VARCHAR(100), mean_value DOUBLE precision 2) |
| No formal schema-compliance component | No `tSchemaComplianceCheck`; validation is structural (Talend's built-in schema propagation) only |

## Filters
**None found.** No `tFilterRow` or `tFilterColumns` components in any of the 4 jobs. All row-level filtering happens upstream in SQL WHERE clauses:
- `companyid = context.companyid AND dates/sessiontimestamp BETWEEN context.startdate AND context.enddate` (tMysqlInput_1, tMysqlInput_2)
- `datasetgroup IN (2,3)` / `=2` / `=3` (tMysqlRow_1 cleanup deletes, scoped per job)

## Reject Logic
**None found.** No `REJECT` connector usage anywhere in the project (`grep connectorName="REJECT"` = 0 matches across all 4 jobs). Error handling falls back to:
- `DIE_ON_ERROR=true` on transform components (tMap) — hard job failure, no reject row stream
- `DIE_ON_ERROR=false` on DB write/delete components — silent continue on row-level write error, no captured reject output

## Validation Summary
| Category | Status | Coverage |
|---|---|---|
| Null checks | Partial | SQL guards + IGNORE_NULL flags only; no explicit null-check component |
| Data quality rules | Partial | Rounding + type casts enforced; no business-rule validation layer |
| Duplicate checks | Partial | UNIQUE_MATCH lookup + UPDATE upsert; no dedicated dedup component |
| Schema validation | Implicit | Talend schema propagation only; no compliance-check component |
| Filters | None (component-level) | All filtering pushed to SQL WHERE clauses |
| Reject logic | **None** | No reject connectors/streams anywhere — all errors are hard-stop or silently ignored |

**Overall risk**: Migration target should add explicit reject-row capture (currently zero visibility into rows that fail tMap transforms or DB writes) and a dedicated dedup/schema-validation stage if migrating off Talend's implicit guarantees.
