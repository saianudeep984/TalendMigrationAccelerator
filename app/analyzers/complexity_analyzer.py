# ── Scoring configuration ──────────────────────────────────────────────────
# These module-level constants are the defaults used by calculate_complexity.
# They are intentionally exposed at module scope (rather than function-local)
# so that the Settings UI ("Scoring" tab) can view and edit them at runtime —
# any changes made via Settings update these dicts/values directly, and
# subsequent calls to calculate_complexity() will use the new values.

# Score weights per component type
# Weights reflect migration complexity: 50=critical, 40=high, 25-35=medium, 5-20=low
WEIGHTS = {
    # ── Custom / Java code ────────────────────────────────────────────────────
    "tJava":              40,
    "tJavaRow":           35,
    "tJavaFlex":          35,
    "tJavaInput":         35,
    "tJavaOutput":        35,
    "tBeanShell":         25,

    # ── OS / system ───────────────────────────────────────────────────────────
    "tSystem":            50,
    "tLibraryLoad":       30,

    # ── Flow control / orchestration ─────────────────────────────────────────
    "tRunJob":            20,
    "tPreJob":            10,
    "tPostJob":           10,
    "tLoop":              10,
    "tFor":               10,
    "tWhile":             10,
    "tFlowToIterate":     10,
    "tIterateToFlow":     10,
    "tSleep":              5,
    "tWarn":               5,
    "tDie":                5,
    "tContinuedFlow":      5,

    # ── Transformation ────────────────────────────────────────────────────────
    "tMap":               10,
    "tXMLMap":            10,
    "tDenormalize":        8,
    "tNormalize":          8,
    "tAggregate":          8,
    "tAggregateRow":       8,
    "tAggregateRows":      8,
    "tUnpivotRow":        10,
    "tPivotToColumnar":   10,
    "tSortRow":            5,
    "tFilterRow":          5,
    "tFilterColumns":      5,
    "tReplaceList":        5,
    "tSetGlobalVar":       5,
    "tFlowMerge":          8,
    "tFlowUnite":          8,
    "tDynamicSchema":     15,
    "tSchemaComplianceCheck": 10,
    "tConvertType":        5,

    # ── File I/O ──────────────────────────────────────────────────────────────
    "tFileInputDelimited":  5,
    "tFileOutputDelimited": 5,
    "tFileInputExcel":      8,
    "tFileOutputExcel":     8,
    "tFileInputJSON":       8,
    "tFileOutputJSON":      8,
    "tFileInputXML":       10,
    "tFileOutputXML":      10,
    "tFileInputPositional": 8,
    "tFileOutputPositional":8,
    "tFileList":            5,
    "tFileCopy":            5,
    "tFileMove":            5,
    "tFileDelete":          5,
    "tFileExist":           5,
    "tFileUnarchive":       5,
    "tFileArchive":         5,
    "tFileInputLDIF":      10,
    "tFileOutputLDIF":     10,
    "tFileCompare":         5,
    "tFileRowCount":        5,

    # ── Database ──────────────────────────────────────────────────────────────
    "tDBInput":             8,
    "tDBOutput":            8,
    "tDBRow":              10,
    "tDBSP":               15,
    "tDBBulkExec":         15,
    "tDBClose":             5,
    "tDBCommit":            5,
    "tDBRollback":          5,
    "tMysqlInput":          8,
    "tMysqlOutput":         8,
    "tMysqlRow":           10,
    "tMysqlBulkExec":      15,
    "tOracleInput":         8,
    "tOracleOutput":        8,
    "tOracleRow":          10,
    "tOracleBulkExec":     15,
    "tMSSqlInput":          8,
    "tMSSqlOutput":         8,
    "tMSSqlRow":           10,
    "tMSSqlBulkExec":      15,
    "tPostgresqlInput":     8,
    "tPostgresqlOutput":    8,
    "tPostgresqlRow":      10,
    "tPostgresqlBulkExec": 15,
    "tDB2Input":            8,
    "tDB2Output":           8,
    "tDB2Row":             10,
    "tSybaseInput":         8,
    "tSybaseOutput":        8,
    "tSybaseRow":          10,
    "tSnowflakeInput":     10,
    "tSnowflakeOutput":    10,
    "tSnowflakeRow":       12,
    "tBigQueryInput":      10,
    "tBigQueryOutput":     10,
    "tRedshiftInput":      10,
    "tRedshiftOutput":     10,
    "tSQLiteInput":         8,
    "tSQLiteOutput":        8,
    "tTeradataInput":       8,
    "tTeradataOutput":      8,
    "tTeradataRow":        10,
    "tHiveInput":          15,
    "tHiveOutput":         15,
    "tHiveRow":            15,
    "tHiveLoad":           20,

    # ── Cloud / big data ──────────────────────────────────────────────────────
    "tS3Put":              10,
    "tS3Get":              10,
    "tS3List":             10,
    "tS3Delete":           10,
    "tAzureBlobInput":     10,
    "tAzureBlobOutput":    10,
    "tAzureSynapseInput":  10,
    "tAzureSynapseOutput": 10,
    "tGCSInput":           10,
    "tGCSOutput":          10,
    "tHDFSInput":          15,
    "tHDFSOutput":         15,
    "tHDFSPut":            15,
    "tHDFSGet":            15,
    "tHDFSList":           15,
    "tSparkSubmit":        20,
    "tParquetInput":       10,
    "tParquetOutput":      10,
    "tAvroInput":          10,
    "tAvroOutput":         10,
    "tDeltaLakeInput":     12,
    "tDeltaLakeOutput":    12,

    # ── Messaging / streaming ─────────────────────────────────────────────────
    "tKafkaInput":         15,
    "tKafkaOutput":        15,
    "tKafkaCommit":        10,
    "tMQOutput":           15,
    "tMQInput":            15,
    "tJMSInput":           15,
    "tJMSOutput":          15,
    "tActiveMQInput":      15,
    "tActiveMQOutput":     15,
    "tRabbitMQInput":      15,
    "tRabbitMQOutput":     15,

    # ── REST / HTTP / SOAP / API ──────────────────────────────────────────────
    "tRESTClient":         25,
    "tRESTRequest":        25,
    "tHTTPRow":            25,
    "tHTTPRequest":        25,
    "tSOAP":               25,
    "tWebService":         25,
    "tWebServiceInput":    25,
    "tWebServiceOutput":   25,
    "tSalesforceInput":    15,
    "tSalesforceOutput":   15,
    "tSalesforceGetUpdated":15,
    "tServiceNowInput":    15,
    "tServiceNowOutput":   15,

    # ── FTP / network ─────────────────────────────────────────────────────────
    "tFTPGet":             10,
    "tFTPPut":             10,
    "tFTPList":            10,
    "tFTPDelete":          10,
    "tSFTPGet":            10,
    "tSFTPPut":            10,
    "tSFTPList":           10,
    "tFTPExists":           5,

    # ── Email ─────────────────────────────────────────────────────────────────
    "tSendMail":           10,
    "tGetMail":            10,

    # ── Logging / monitoring ──────────────────────────────────────────────────
    "tLogRow":              5,
    "tLogCatcher":          5,
    "tStatCatcher":         5,
    "tFlowMeter":           5,
    "tAssertCatcher":       5,
    "tWaitForFile":         8,
    "tWaitForFileList":     8,

    # ── Lookup / join ─────────────────────────────────────────────────────────
    "tHashInput":           5,
    "tHashOutput":          5,
    "tCacheInput":          8,
    "tCacheOutput":         8,
    "tLookupInput":         8,
    "tLookupOutput":        8,
    "tMatchGroup":         15,

    # ── Data quality ──────────────────────────────────────────────────────────
    "tDataMasking":        15,
    "tDataStewardship":    15,
    "tRuleSurvival":       15,
    "tDqReportRun":        15,

    # ── ELT / generation ─────────────────────────────────────────────────────
    "tELTInput":           10,
    "tELTOutput":          10,
    "tELTMap":             12,
    "tELTUnion":           10,
    "tELTDifference":      10,
    "tELTIntersect":       10,

    # ── SAP ───────────────────────────────────────────────────────────────────
    "tSAPInput":           20,
    "tSAPOutput":          20,
    "tSAPIDocInput":       25,
    "tSAPIDocOutput":      25,
    "tSAPBapiInput":       25,
    "tSAPBapiOutput":      25,

    # ── Talend internal / misc ────────────────────────────────────────────────
    "tRowGenerator":        5,
    "tFixedFlowInput":      5,
    "tBlank":               3,
    "tBuffer":              5,
    "tUnite":               5,
    "tSampleRow":           5,
    "tContextLoad":        10,
    "tContextDump":        10,
    "tContextToFlow":       8,
    "tJobletInput":        10,
    "tJobletOutput":       10,
}

RISK_LABELS = {
    # Custom / Java
    "tJava":              "Custom Java Code",
    "tJavaRow":           "Custom Java Code",
    "tJavaFlex":          "Custom Java Code",
    "tJavaInput":         "Custom Java Code",
    "tJavaOutput":        "Custom Java Code",
    "tBeanShell":         "Deprecated BeanShell Scripting",
    # OS / system
    "tSystem":            "OS Command Execution",
    "tLibraryLoad":       "External Library Dependency",
    # Orchestration
    "tRunJob":            "Job Dependency",
    "tPreJob":            "Job Dependency",
    "tPostJob":           "Job Dependency",
    # Messaging
    "tKafkaInput":        "Streaming — Kafka",
    "tKafkaOutput":       "Streaming — Kafka",
    "tMQOutput":          "Message Queue",
    "tMQInput":           "Message Queue",
    "tJMSInput":          "Message Queue — JMS",
    "tJMSOutput":         "Message Queue — JMS",
    "tActiveMQInput":     "Message Queue — ActiveMQ",
    "tActiveMQOutput":    "Message Queue — ActiveMQ",
    "tRabbitMQInput":     "Message Queue — RabbitMQ",
    "tRabbitMQOutput":    "Message Queue — RabbitMQ",
    # REST / HTTP
    "tRESTClient":        "REST Integration",
    "tRESTRequest":       "REST Integration",
    "tHTTPRow":           "REST Integration",
    "tHTTPRequest":       "REST Integration",
    "tSOAP":              "SOAP/Web Service Integration",
    "tWebService":        "SOAP/Web Service Integration",
    "tWebServiceInput":   "SOAP/Web Service Integration",
    "tWebServiceOutput":  "SOAP/Web Service Integration",
    # Cloud
    "tHDFSInput":         "HDFS / Hadoop",
    "tHDFSOutput":        "HDFS / Hadoop",
    "tHDFSPut":           "HDFS / Hadoop",
    "tHDFSGet":           "HDFS / Hadoop",
    "tSparkSubmit":       "Spark Execution",
    "tHiveInput":         "Hive / Hadoop SQL",
    "tHiveOutput":        "Hive / Hadoop SQL",
    "tHiveRow":           "Hive / Hadoop SQL",
    "tHiveLoad":          "Hive / Hadoop SQL",
    # Databases
    "tDBSP":              "Stored Procedure",
    "tDBBulkExec":        "Bulk DB Execution",
    "tMysqlBulkExec":     "Bulk DB Execution",
    "tOracleBulkExec":    "Bulk DB Execution",
    "tMSSqlBulkExec":     "Bulk DB Execution",
    "tPostgresqlBulkExec":"Bulk DB Execution",
    # SAP
    "tSAPInput":          "SAP Integration",
    "tSAPOutput":         "SAP Integration",
    "tSAPIDocInput":      "SAP iDoc Integration",
    "tSAPIDocOutput":     "SAP iDoc Integration",
    "tSAPBapiInput":      "SAP BAPI Integration",
    "tSAPBapiOutput":     "SAP BAPI Integration",
    # Salesforce
    "tSalesforceInput":   "Salesforce CRM",
    "tSalesforceOutput":  "Salesforce CRM",
    "tSalesforceGetUpdated":"Salesforce CRM",
    "tServiceNowInput":   "ServiceNow Integration",
    "tServiceNowOutput":  "ServiceNow Integration",
    # Data quality
    "tDataMasking":       "Data Masking / PII",
    "tDataStewardship":   "Data Quality",
    "tMatchGroup":        "Data Quality — Matching",
    "tDqReportRun":       "Data Quality Report",
    # Dynamic / ELT
    "tDynamicSchema":     "Dynamic Schema — Needs Review",
    "tELTMap":            "ELT Mapping",
    # Lookup
    "tContextLoad":       "Context Variable Load",
    "tContextDump":       "Context Variable Dump",
    "tJobletInput":       "Joblet Dependency",
    "tJobletOutput":      "Joblet Dependency",
}

DEFAULT_WEIGHT = 5

# Complexity level score thresholds (upper-bound, exclusive). A score below
# THRESHOLDS["LOW"] is LOW, below THRESHOLDS["MEDIUM"] is MEDIUM, below
# THRESHOLDS["HIGH"] is HIGH, otherwise CRITICAL.
THRESHOLDS = {
    "LOW":    50,
    "MEDIUM": 100,
    "HIGH":   200,
}

# Estimated migration effort (hours) by readiness category. Used by pages
# that translate complexity level into an effort estimate.
EFFORT_HOURS = {
    "manual": 8,
    "auto":   2,
}


def calculate_complexity(job_data, weights=None, risk_labels=None, default_weight=None, thresholds=None):
    """
    Calculate job complexity in a single pass over components.

    Components are dicts: {"component_type": str, "unique_name": str, ...}
    Risk factors are deduplicated (one entry per factor type, not per component
    instance) so a job with 10 tJava nodes doesn't produce 10 identical labels.

    Optional overrides (weights, risk_labels, default_weight, thresholds) let
    callers (e.g. the Settings -> Scoring page) supply user-edited scoring
    configuration without mutating the module defaults. If omitted, the
    current module-level WEIGHTS / RISK_LABELS / DEFAULT_WEIGHT / THRESHOLDS
    are used.
    """

    weights = weights if weights is not None else WEIGHTS
    risk_labels = risk_labels if risk_labels is not None else RISK_LABELS
    default_weight = default_weight if default_weight is not None else DEFAULT_WEIGHT
    thresholds = thresholds if thresholds is not None else THRESHOLDS

    score = 0
    seen_risk_factors: set = set()
    risk_factors = []

    for component in job_data.get("components", []):

        # components are dicts
        comp_type = (
            component.get("component_type", "")
            if isinstance(component, dict)
            else str(component)
        )

        score += weights.get(comp_type, default_weight)

        label = risk_labels.get(comp_type)
        if label and label not in seen_risk_factors:
            seen_risk_factors.add(label)
            risk_factors.append(label)

    if score < thresholds["LOW"]:
        level = "LOW"
    elif score < thresholds["MEDIUM"]:
        level = "MEDIUM"
    elif score < thresholds["HIGH"]:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return {
        "score": score,
        "complexity": level,
        "complexity_band": level,
        "risk_factors": risk_factors
    }
