# TMA Security Architecture — Update_mean_max

## Detection Results
| Element | Found | Detail |
|---|---|---|
| Credentials Usage | DB connections only | MySQL USER/PASS on every tMysqlInput/tMysqlOutput/tMysqlRow node across all 4 jobs (5 nodes per ETL job) |
| Encrypted Context Variables | Inconsistent | Only `Test_Plugin_Max_values` defines `localhost_Sriyaplugin_Password` as `type="id_Password"` (Talend's reversibly-obfuscated context type). `GA_Max_values`, `Plugin_Max_values`, `Update_mean_max` define `password` as `type="id_String"` with the **plaintext value visible** in the XML (`indiawin01`, `root`) |
| SSL Connections | **0** | No `useSSL`, `enabledSSLProtocol`, or SSL-related JDBC parameter found anywhere; only additional param present is `noDatetimeStringSync=true` — connections default to unencrypted MySQL transport |
| Vault References | **0** | No HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, or keystore reference anywhere in the project |
| Hardcoded Passwords | **Yes — systemic** | Every DB component's `PASS` field is a literal obfuscated string embedded directly on the node (e.g. `PASS="8pW6Nmy2kuczSBOgoJ7Ub24fQgd+SRSj"`), **not** `context.password` — the context password variable exists but is bypassed entirely at the connection level |

## Evidence Summary
- USER field correctly uses `context.username` on all DB nodes (good practice).
- PASS field uses a literal Talend-obfuscated string on every single DB node instead of `context.password`, across all 4 jobs — credentials are baked into the job XML itself, not externalized.
- Context-level `password` variable in 3 of 4 jobs is typed `id_String` (plaintext-stored) rather than `id_Password`, and even if it were used, plaintext default values (`indiawin01`, `root`) are committed directly in the repository.
- Talend's obfuscation (`id_Password` reversible cipher) is not encryption — it is trivially reversible and is not a substitute for a vault/secrets manager regardless.

## RAG Risk Table
| Risk Area | Rating | Justification |
|---|---|---|
| Hardcoded passwords on DB nodes | **RED** | Systemic across all 4 jobs, all 5 DB components per job — credentials live in version-controlled XML, fully recoverable (Talend obfuscation is reversible) |
| Plaintext context password values | **RED** | `indiawin01` / `root` stored as plaintext `id_String` context defaults in 3 of 4 jobs — visible to anyone with repo/XML access |
| No SSL/TLS on DB connections | **RED** | Zero SSL configuration found; credentials and data travel unencrypted between Talend and MySQL |
| No vault/secrets manager integration | **RED** | No external secrets store; all credential management is file-based and manual |
| Inconsistent context typing (id_Password vs id_String) | **AMBER** | One job (Test_Plugin_Max_values) uses the correct obfuscated type while production jobs (GA_Max_values, Plugin_Max_values, Update_mean_max) do not — inconsistent baseline, and even the correct type isn't real encryption |
| Username externalization | **GREEN** | USER consistently uses `context.username` rather than hardcoding, across all DB nodes in all jobs |

## Overall Security Posture: **RED**
4 of 6 detection categories rate RED. Recommend before any migration or redeployment: (1) remove all hardcoded PASS values and route through `context.password`, (2) move credentials to a vault/secrets manager (not Talend's reversible obfuscation), (3) enable `useSSL=true` (plus certificate validation) on all MySQL connection strings, (4) purge plaintext password defaults from context definitions and rotate the exposed credentials (`indiawin01`, `root`).
