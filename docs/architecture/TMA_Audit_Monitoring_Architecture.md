# TMA Audit & Monitoring Architecture — Update_mean_max
Scanned all 4 job items for audit tables, logging framework settings, batch/run identifiers, row-count tracking, execution logs, and monitoring components.

## Detection Results
| Element | Found | Detail |
|---|---|---|
| Audit Tables | **0** | No table named/referenced with audit, batch_id, run_id, or execution_log patterns anywhere in SQL or schema |
| Logging Framework | **Disabled** | `STATANDLOG_USE_PROJECT_SETTINGS=false`, `ON_STATCATCHER_FLAG=false`, `CATCH_REALTIME_STATS=false` on all 4 jobs — Talend's built-in stats/log catcher is explicitly turned off project-wide |
| Batch IDs | **0** | No batch_id, run_id, or job-instance identifier column/variable in any schema or SQL |
| Row Counts | **0** | No `NB_LINE`/`globalMap` row-count capture; no component persists rows-processed/rows-written counts anywhere |
| Execution Logs | **0** | No execution-log table or file write; `FILENAME_STATS="stats_file.txt"` is configured but unused since `CATCH_REALTIME_STATS=false` |
| Monitoring Components | **0** | No tStatCatcher, tFlowMeter, tFlowMeterCatcher, tLogCatcher, or tAuditLog components in any job |

## Closest Existing Signals (not true audit/monitoring)
| Item | Role | Why it doesn't count |
|---|---|---|
| tLogRow_1 / tLogRow_2 (GA_Max_values, Plugin_Max_values) | Console row dump after successful write | Ephemeral — prints to execution console only, nothing persisted; runs only on success path |
| Process_Date column (`TalendDate.getCurrentDate()`) | Written into `mean_values` / `ga_hourly_parameter_configuration` business tables | Business data field for KPI freshness, not a job-run audit timestamp; carries no run/batch identity |
| tMysqlRow_1 cleanup DELETE | Pre-run cleanup of `mean_values` by companyid/datasetgroup | Operational housekeeping, not an audit record of what ran |

## Flagged Gaps
1. **No audit table** — there is no persisted record of when a job ran, for which companyid/date range, how many rows were processed, or whether it succeeded.
2. **Stats/logging framework explicitly disabled** — the project sets every Talend stats-catching flag to `false`, meaning even the built-in runtime stats (rows/sec, component timing) are unavailable.
3. **No batch or run identifier** — concurrent or repeated runs for the same companyid (e.g. reprocessing a date range) are indistinguishable; no way to trace a row back to the job execution that produced it.
4. **No row-count reconciliation** — no mechanism compares rows read (tMysqlInput_1/_2) vs. rows written (tMysqlOutput_1/_2), so silent data loss (also flagged in Error Handling Architecture due to `DIE_ON_ERROR=false` on writes) would go undetected.
5. **No execution log persistence** — `tLogRow` output is console-only and lost once the job finishes; nothing survives for post-run troubleshooting or compliance review.
6. **No monitoring component** — no tStatCatcher/tFlowMeterCatcher subjob exists to centrally capture performance/volume metrics across the Update_mean_max → Plugin_Max_values/GA_Max_values orchestration chain.

## Audit Framework Status: **MISSING**
This project has no audit or monitoring framework. Migration target should introduce: (a) a dedicated audit table (run_id, job_name, companyid, start/end timestamp, status, row counts in/out), (b) re-enable or replace Talend stats catching with structured logging, (c) wire a batch/run id through context variables into every write, and (d) reconcile read vs. write row counts per execution.
