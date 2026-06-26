# TMA Performance Architecture — Update_mean_max

## Detection Results
| Element | Found | Detail |
|---|---|---|
| Parallel Execution | **0** | No parallel subjob orchestration; Update_mean_max runs tRunJob_1 → tRunJob_3 strictly sequentially (OnSubjobOk chain) |
| tParallelize | **0** | No instances in any of the 4 jobs |
| Partitioning | **0** | No tPartitioner/tDepartitionRecombiner; no data partitioning anywhere |
| Lookup Strategy | Load-once, unparallelized | `LKUP_PARALLELIZE=false` on every tMap (GA_Max_values, Plugin_Max_values, Test_Plugin_Max_values); lookup table (tMysqlInput_2) loaded fully into memory with no LIMIT/pagination, scoped only by `companyid` |
| Large Datasets | Present (DB-side) | tMysqlInput_1 query has 6 nested `FROM` levels (pivot-then-aggregate pattern) — CPU/memory load pushed onto MySQL, not Talend |
| Memory Intensive Components | tMap x4, tUnpivotRow x2, tAggregateRow x1 per job | `ROWS_BUFFER_SIZE=2000000` per tMap; `ENABLE_STREAM=false` on both tMysqlInput components (full result set loaded before processing); no `USE_DISK` spill setting on tAggregateRow (pure in-memory aggregation) |

## Bottlenecks Identified
1. **Sequential subjob execution** — Plugin_Max_values and GA_Max_values are independent (different source tables: `plugin_master_data` vs `ga_master_data`) but run one after another via tRunJob chaining instead of in parallel, doubling wall-clock time unnecessarily.
2. **Unparallelized lookup load** — `LKUP_PARALLELIZE=false` means tMap_3's lookup (`ga_hourly_parameter_configuration`) loads single-threaded before the main flow can proceed, serializing what could overlap with upstream processing.
3. **DB-side pivot complexity** — the 6-level nested subquery in tMysqlInput_1 (raw rows → CASE-pivot → outer AVG/STDDEV) runs entirely in MySQL with no indexed intermediate step visible; large date ranges or company datasets will scale this query non-linearly.
4. **No streaming on large reads** — `ENABLE_STREAM=false` on tMysqlInput_1/_2 forces full result-set buffering in Talend's JVM heap before the first row is emitted downstream, increasing peak memory for large company/date-range combinations.
5. **Unpivot fan-out amplification** — each tUnpivotRow expands 1 input row into ~20 output rows (one per Mean_P*/Max_P* column); combined with `ROWS_BUFFER_SIZE=2000000` per downstream tMap, this is the largest realistic memory multiplier in the flow.
6. **No disk-spill protection on aggregation** — tAggregateRow_1 has no `USE_DISK` setting, so a larger-than-expected unpivoted dataset could exhaust JVM heap rather than spilling to disk.
7. **Single-row-at-a-time risk on lookup match** — `UNIQUE_MATCH` lookup mode on tMap_3 adds per-row matching overhead proportional to lookup table size, with no index/parallel hint configured.

## Optimization Recommendations
| Area | Recommendation |
|---|---|
| Orchestration | Run Plugin_Max_values and GA_Max_values in parallel subjobs (independent data sources) instead of sequential tRunJob chaining — halves orchestration wall-clock time |
| Lookup | Enable `LKUP_PARALLELIZE=true` on tMap_3 in all 3 ETL jobs; add an index on `ga_hourly_parameter_configuration(companyid, paramId)` / `individual_parameter_configuration(companyid, parameterid)` to speed the lookup query and the UNIQUE_MATCH join |
| Source read | Set `ENABLE_STREAM=true` on tMysqlInput_1/_2 where downstream components support streaming, to reduce peak memory and start processing before the full result set arrives |
| DB query | Push the inner pivot/aggregation subquery into a materialized view or indexed staging table if `ga_master_data`/`plugin_master_data` grow large — avoids re-computing the 6-level nested query on every run |
| Buffer sizing | Right-size `ROWS_BUFFER_SIZE` (currently 2,000,000 per tMap) based on actual row volume per companyid/date-range rather than a flat default, to avoid over-allocating JVM heap across 4 tMap instances per job |
| Aggregation | Enable disk-spill (`USE_DISK`) on tAggregateRow_1 as a safety net against unexpectedly large unpivoted datasets |
| Batch writes | Current `COMMIT_EVERY=10000` / `BATCH_SIZE=10000` on both tMysqlOutput components is reasonable — no change needed unless write volume grows by an order of magnitude |
