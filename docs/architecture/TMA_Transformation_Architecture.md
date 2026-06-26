# Transformation Mapping Architecture (TMA) — Update_mean_max

**Source:** Talend DI project `sriyamlxigaapi` | **Jobs:** Update_mean_max_0.1 (orchestrator) → Plugin_Max_values_1.0 / GA_Max_values_1.0 (identical logic, v1.0)
**No tJava / tJavaRow / tFilterRow components found in this project.**

## Job Flow
```
Update_mean_max (0.1)
 ├─ tMysqlRow_1: DELETE mean_values WHERE companyid=? AND datasetgroup IN (2,3)
 ├─ tRunJob_1 → Plugin_Max_values (passes: companyid, startdate, enddate, host, port, username, password, database)
 └─ tRunJob_3 → GA_Max_values     (same context params)

GA_Max_values / Plugin_Max_values (identical):
tMysqlInput_1 → tMap_1 → tUnpivotRow_1 → tMap_2 → tAggregateRow_1 → tMap_3 → tMysqlOutput_1 → tLogRow_1
                tMap_1 → tUnpivotRow_2 → tMap_4 → tMysqlOutput_2 → tLogRow_2
                                          tMap_3 ← tMysqlInput_2 (lookup)
```

## Component Table

| Component | Type | Logic | Target |
|---|---|---|---|
| tMysqlInput_1 | Source/Aggregation (SQL) | Pivoted AVG/STDDEV per paramid (P1–P19) over `ga_master_data` filtered by `companyid=context.companyid AND dates BETWEEN context.startdate AND context.enddate`; computes Mean & MAX(=AVG+3·STDDEV) KPIs (visits, page views, bounce rate, abandonment, repeat users, page load time, etc.) | tMap_1 |
| tMap_1 | tMap Logic | Passthrough/reshape of 40 KPI columns (companyid + 20 Mean/Max pairs P1–P5 shown in schema) into row for unpivoting | tUnpivotRow_1, tUnpivotRow_2 |
| tUnpivotRow_1 | Unpivot | Row key = `companyid`; unpivots all Mean_* columns → `pivot_key`/`pivot_value` | tMap_2 |
| tUnpivotRow_2 | Unpivot | Row key = `companyid`; unpivots all Max_* columns → `pivot_key`/`pivot_value` | tMap_4 |
| tMap_2 | tMap Logic | Maps unpivoted Mean rows to aggregation input schema (companyid, datasetgroup, paramid, mean_value, max_value, Process_Date) | tAggregateRow_1 |
| tAggregateRow_1 | Aggregation | **Group by:** paramid. **Operations:** `mean_value`=MAX(mean_value, ignore null), `max_value`=MAX(max_value, ignore null), `companyid`=FIRST, `datasetgroup`=FIRST, `Process_Date`=FIRST | tMap_3 |
| tMysqlInput_2 | Lookup Source (SQL) | `SELECT id, companyid, paramId, Type, Catagory, max_Value, mean_Value FROM ga_hourly_parameter_configuration WHERE companyid=context.companyid` | tMap_3 (lookup input) |
| tMap_3 | tMap Logic + Lookup | Joins aggregated stream (main, row4) with `ga_hourly_parameter_configuration` lookup (row3) on companyid/paramid context | tMysqlOutput_1 |
| tMysqlOutput_1 | Target (DB write) | Writes joined/enriched rows to table `ga_hourly_parameter_configuration` | tLogRow_1 |
| tLogRow_1 | Log | Console log of rows written to `ga_hourly_parameter_configuration` | — |
| tMap_4 | tMap Logic | Maps unpivoted Max rows to output schema (mirrors tMap_2 for Max dataset, datasetgroup=3) | tMysqlOutput_2 |
| tMysqlOutput_2 | Target (DB write) | Writes rows to table `mean_values` | tLogRow_2 |
| tLogRow_2 | Log | Console log of rows written to `mean_values` | — |
| tMysqlRow_1 (orchestrator) | Pre-cleanup SQL | `DELETE FROM mean_values WHERE companyid=context.companyid AND datasetgroup IN (2,3)` | precedes tRunJob calls |
| tRunJob_1 | Surrogate/Orchestration | Invokes `Plugin_Max_values` job, propagates 8 context params | Plugin_Max_values job |
| tRunJob_3 | Surrogate/Orchestration | Invokes `GA_Max_values` job, propagates 8 context params | GA_Max_values job |

## Context Variables
| Variable | Sample Value | Used By |
|---|---|---|
| companyid | SO575859 / XY432126 | All SQL WHERE clauses |
| startdate / StartDate | 2016-01-01 | tMysqlInput_1 date filter |
| enddate / EndDate | 2016-02-04 | tMysqlInput_1 date filter |
| host | 54.88.209.139 / localhost | DB connection |
| port | 3306 | DB connection |
| username | mlxitest / root | DB connection |
| password | (encrypted/plain per env) | DB connection |
| database | sriyaplugin | DB connection |

## Data Conversions
- Numeric rounding: `ROUND(AVG(...),2)` applied to all 20 KPI pairs in tMysqlInput_1.
- Type casts via schema: VARCHAR→id_String, DOUBLE→id_Double, INT→id_Integer, DATETIME→id_Date (pattern `dd-MM-yyyy`).
- Division-by-zero guards: `IF(P1=0,1,P1)` pattern used for ratio KPIs.

## Surrogate Keys
- No explicit tSurrogateKey/auto-increment component found; `id` column in `ga_hourly_parameter_configuration` (lookup/target) is DB-managed.
- `datasetgroup` acts as a discriminator key (2=Mean, 3=Max) distinguishing dataset partitions written to `mean_values`.

## Filters
- No tFilterRow/tFilterColumns component present. Filtering is performed in SQL WHERE clauses (tMysqlInput_1, tMysqlInput_2, tMysqlRow_1) on `companyid` and date range.

## tJava / tJavaRow Logic
- **None present** in this project (no tJava, tJavaRow, or tJavaFlex components found across all 4 job items).
