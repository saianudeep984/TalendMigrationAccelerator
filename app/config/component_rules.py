# -------------------------------------------------------
# KNOWN TALEND 8 / CLOUD STANDARD COMPONENTS
# (everything NOT in this set is flagged as custom/unknown)
# -------------------------------------------------------

TALEND8_KNOWN_COMPONENTS = {
    # Core Flow
    "tFlowToIterate", "tIterateToFlow", "tAggregateRow", "tSortRow",
    "tUniqueRow", "tSampleRow", "tFilterRow", "tDenormalize", "tNormalize",
    "tMap", "tJoin", "tFuzzyMatch", "tSetGlobalVar", "tContextLoad",
    "tContextDump", "tFixedFlowInput", "tRowGenerator", "tFlowToIterate",
    "tBufferInput", "tBufferOutput",

    # DB Generic
    "tDBInput", "tDBOutput", "tDBRow", "tDBCommit", "tDBRollback",
    "tDBClose", "tDBConnection", "tDBSCD", "tDBSCDELT",

    # MySQL
    "tMysqlInput", "tMysqlOutput", "tMysqlRow", "tMysqlConnection",
    "tMysqlCommit", "tMysqlClose", "tMysqlRollback",

    # Oracle
    "tOracleInput", "tOracleOutput", "tOracleRow", "tOracleConnection",
    "tOracleCommit", "tOracleClose", "tOracleRollback", "tOracleSCD",

    # MSSQL
    "tMSSqlInput", "tMSSqlOutput", "tMSSqlRow", "tMSSqlConnection",
    "tMSSqlCommit", "tMSSqlClose", "tMSSqlRollback",

    # Teradata
    "tTeradataInput", "tTeradataOutput", "tTeradataRow",
    "tTeradataConnection", "tTeradataCommit", "tTeradataClose",
    "tTeradataRollback", "tTeradataFastLoad", "tTeradataTPT",

    # JDBC (generic driver)
    "tJDBCInput", "tJDBCOutput", "tJDBCRow", "tJDBCConnection",
    "tJDBCCommit", "tJDBCClose", "tJDBCRollback",

    # PostgreSQL
    "tPostgresqlInput", "tPostgresqlOutput", "tPostgresqlRow",
    "tPostgresqlConnection", "tPostgresqlCommit", "tPostgresqlClose",

    # DB2
    "tDB2Input", "tDB2Output", "tDB2Row", "tDB2Connection",
    "tDB2Commit", "tDB2Close",

    # Sybase / SAP ASE
    "tSybaseInput", "tSybaseOutput", "tSybaseRow", "tSybaseConnection",
    "tSybaseCommit", "tSybaseClose",

    # Snowflake
    "tSnowflakeInput", "tSnowflakeOutput", "tSnowflakeRow",
    "tSnowflakeConnection", "tSnowflakeClose",

    # Redshift
    "tRedshiftInput", "tRedshiftOutput", "tRedshiftRow",
    "tRedshiftConnection", "tRedshiftClose",

    # BigQuery
    "tBigQueryInput", "tBigQueryOutput",

    # Hive / Hadoop
    "tHiveInput", "tHiveOutput", "tHiveRow", "tHiveConnection",
    "tHiveClose", "tHDFSGet", "tHDFSPut", "tHDFSList", "tHDFSDelete",
    "tHDFSInput", "tHDFSOutput",

    # Spark
    "tSparkConfiguration", "tSparkSubmit",

    # SAP
    "tSAPInput", "tSAPOutput", "tSAPBAPIInput", "tSAPBAPIOutput",
    "tSAPConnectionCreate", "tSAPConnectionClose",

    # Salesforce
    "tSalesforceInput", "tSalesforceOutput", "tSalesforceBulkExec",
    "tSalesforceGetDeleted", "tSalesforceConnection", "tSalesforceClose",

    # File
    "tFileInputDelimited", "tFileOutputDelimited", "tFileInputExcel",
    "tFileOutputExcel", "tFileInputJSON", "tFileOutputJSON",
    "tFileInputXML", "tFileOutputXML", "tFileList", "tFileCopy",
    "tFileDelete", "tFileMove", "tFileExist", "tFileArchive",
    "tFileUnarchive", "tFileInputPositional", "tFileOutputPositional",
    "tFileInputMSXML", "tFileOutputMSXML", "tFileCompare",
    "tFileInputLDIF", "tFileOutputLDIF", "tFileInputRegex",
    "tFileOutputRaw", "tFileInputRaw",

    # FTP / SFTP
    "tFTPGet", "tFTPPut", "tFTPList", "tFTPDelete", "tFTPConnection",
    "tFTPClose", "tSFTPGet", "tSFTPPut", "tSFTPList", "tSFTPDelete",
    "tSFTPConnection", "tSFTPClose",

    # Email
    "tSendMail", "tSendMailAttachment", "tGetMail",

    # Log / Control
    "tLogRow", "tLogCatcher", "tDie", "tWarn", "tAssertCatcher",
    "tAssertEquals", "tPrejob", "tPostjob", "tSleep", "tStatCatcher",
    "tFlowMeterCatcher",

    # Java / Script
    "tJava", "tJavaRow", "tJavaFlex", "tBeanShell", "tGroovy",
    "tPythonRow", "tRubyRow",

    # System / OS
    "tSystem", "tLibraryLoad", "tFlowMeter",

    # Orchestration
    "tRunJob", "tLoop", "tFor", "tRecollect", "tParallelize",
    "tSynchronize", "tWaitForFile",

    # Messaging
    "tKafkaInput", "tKafkaOutput", "tActiveMQInput", "tActiveMQOutput",
    "tRabbitMQInput", "tRabbitMQOutput", "tJMSInput", "tJMSOutput",
    "tJMSConnectionFactory", "tJMSClose",

    # REST / HTTP / Web services
    "tRESTClient", "tHTTPRow", "tHTTPRequest", "tSOAP", "tWebService",
    "tWebServiceInput", "tWebServiceOutput",

    # Cloud — AWS
    "tS3Get", "tS3Put", "tS3List", "tS3Delete",
    "tDynamoDBInput", "tDynamoDBOutput",

    # Cloud — Azure
    "tAzureBlobInput", "tAzureBlobOutput",
    "tAzureSynapseInput", "tAzureSynapseOutput",
    "tAzureCosmosDBInput", "tAzureCosmosDBOutput",

    # Cloud — GCP
    "tGCSGet", "tGCSPut", "tGCSList",

    # XML / JSON helpers
    "tWriteJSONField", "tExtractJSONFields", "tXMLMap",
    "tParseJSON", "tExtractXMLField",

    # Schema / Data quality
    "tSchemaComplianceCheck", "tReplaceList", "tConvertType",
    "tNormalize",

    # Lookup / Cache
    "tHashInput", "tHashOutput",
}

# -------------------------------------------------------
# DEPRECATED: component → replacement in T8
# -------------------------------------------------------

DEPRECATED_COMPONENT_MAP = {
    "tMysqlInput":       {"replacement": "tDBInput",      "auto_fix": True,  "risk": "MEDIUM"},
    "tMysqlOutput":      {"replacement": "tDBOutput",     "auto_fix": True,  "risk": "MEDIUM"},
    "tMysqlRow":         {"replacement": "tDBRow",        "auto_fix": True,  "risk": "MEDIUM"},
    "tMysqlConnection":  {"replacement": "tDBConnection", "auto_fix": True,  "risk": "MEDIUM"},
    "tMysqlCommit":      {"replacement": "tDBCommit",     "auto_fix": True,  "risk": "LOW"},
    "tOracleInput":      {"replacement": "tDBInput",      "auto_fix": True,  "risk": "MEDIUM"},
    "tOracleOutput":     {"replacement": "tDBOutput",     "auto_fix": True,  "risk": "MEDIUM"},
    "tOracleRow":        {"replacement": "tDBRow",        "auto_fix": True,  "risk": "MEDIUM"},
    "tOracleConnection": {"replacement": "tDBConnection", "auto_fix": True,  "risk": "MEDIUM"},
    "tOracleCommit":     {"replacement": "tDBCommit",     "auto_fix": True,  "risk": "LOW"},
    "tMSSqlInput":       {"replacement": "tDBInput",      "auto_fix": True,  "risk": "MEDIUM"},
    "tMSSqlOutput":      {"replacement": "tDBOutput",     "auto_fix": True,  "risk": "MEDIUM"},
    "tMSSqlRow":         {"replacement": "tDBRow",        "auto_fix": True,  "risk": "MEDIUM"},
    "tMSSqlConnection":  {"replacement": "tDBConnection", "auto_fix": True,  "risk": "MEDIUM"},
    "tMSSqlCommit":      {"replacement": "tDBCommit",     "auto_fix": True,  "risk": "LOW"},
    "tMSSqlClose":       {"replacement": "tDBClose",      "auto_fix": True,  "risk": "LOW"},
    "tMSSqlRollback":    {"replacement": "tDBRollback",   "auto_fix": True,  "risk": "LOW"},
    "tMysqlClose":       {"replacement": "tDBClose",      "auto_fix": True,  "risk": "LOW"},
    "tMysqlRollback":    {"replacement": "tDBRollback",   "auto_fix": True,  "risk": "LOW"},
    "tOracleClose":      {"replacement": "tDBClose",      "auto_fix": True,  "risk": "LOW"},
    "tOracleRollback":   {"replacement": "tDBRollback",   "auto_fix": True,  "risk": "LOW"},
    "tOracleSCD":        {"replacement": "tDBSCD",        "auto_fix": True,  "risk": "MEDIUM"},
    "tFileInputExcel":   {"replacement": "tFileInputExcel (T8 OK)", "auto_fix": False, "risk": "LOW"},
    "tFileInputMSXML":   {"replacement": "tFileInputXML",  "auto_fix": False, "risk": "MEDIUM"},
    "tFileOutputMSXML":  {"replacement": "tFileOutputXML", "auto_fix": False, "risk": "MEDIUM"},
    "tAzureStorageGet":  {"replacement": "tAzureBlobInput",  "auto_fix": True,  "risk": "LOW"},
    "tAzureStoragePut":  {"replacement": "tAzureBlobOutput", "auto_fix": True,  "risk": "LOW"},
    "tAzureStorageList": {"replacement": "tAzureBlobInput",  "auto_fix": False, "risk": "LOW"},
    "tS3Connection":     {"replacement": "tS3Get / tS3Put",  "auto_fix": False, "risk": "LOW"},
    "tMom":              {"replacement": "tKafkaInput / tActiveMQInput", "auto_fix": False, "risk": "HIGH"},
    "tESBConsumer":      {"replacement": "tRESTClient",      "auto_fix": False, "risk": "HIGH"},
    "tRESTRequest":      {"replacement": "tRESTClient",      "auto_fix": False, "risk": "MEDIUM"},
    "tRESTResponse":     {"replacement": "tRESTClient",      "auto_fix": False, "risk": "MEDIUM"},
    "tSOAP11":           {"replacement": "tSOAP",            "auto_fix": True,  "risk": "MEDIUM"},
    "tSOAP12":           {"replacement": "tSOAP",            "auto_fix": True,  "risk": "MEDIUM"},
    "tServiceActivity":  {"replacement": "tRESTClient",      "auto_fix": False, "risk": "HIGH"},
    "tRouteInput":       {"replacement": "tJMSInput",        "auto_fix": False, "risk": "HIGH"},
    "tRouteOutput":      {"replacement": "tJMSOutput",       "auto_fix": False, "risk": "HIGH"},
    "tWebService":       {"replacement": "tRESTClient",      "auto_fix": False, "risk": "MEDIUM"},
    "tDataMasking":      {"replacement": "tMap",             "auto_fix": False, "risk": "HIGH"},
    "tDataStewardship":  {"replacement": "External DQ stewardship portal", "auto_fix": False, "risk": "HIGH"},
    "tRuleSurvival":     {"replacement": "tMap",             "auto_fix": False, "risk": "MEDIUM"},
    "tDqReportRun":      {"replacement": "External Data Quality Portal reporting", "auto_fix": False, "risk": "MEDIUM"},
    "tMatchGroup":       {"replacement": "tUniqueRow",       "auto_fix": False, "risk": "HIGH"},
    "tSurvivorshipMerge":{"replacement": "tMap",             "auto_fix": False, "risk": "MEDIUM"},
    "tRecordMatching":   {"replacement": "tUniqueRow",       "auto_fix": False, "risk": "HIGH"},
    "tDataQuality":      {"replacement": "External Data Quality service", "auto_fix": False, "risk": "MEDIUM"},
    "tStandardize":      {"replacement": "tReplace",         "auto_fix": False, "risk": "MEDIUM"},
    "tAddressRow":       {"replacement": "tRESTClient",      "auto_fix": False, "risk": "MEDIUM"},
    "tMDMInput":         {"replacement": "tRESTClient",      "auto_fix": False, "risk": "HIGH"},
    "tMDMOutput":        {"replacement": "tRESTClient",      "auto_fix": False, "risk": "HIGH"},
    "tMDMConnection":    {"replacement": "tRESTClient",      "auto_fix": False, "risk": "MEDIUM"},
    "tMDMCommit":        {"replacement": "tRESTClient",      "auto_fix": False, "risk": "LOW"},
    "tMDMDelete":        {"replacement": "tRESTClient",      "auto_fix": False, "risk": "HIGH"},
    "tMDMBulkLoad":       {"replacement": "tRESTClient",      "auto_fix": False, "risk": "HIGH"},
    "tBeanShell":        {"replacement": "tJavaRow",      "auto_fix": False, "risk": "HIGH"},
    "tJavaFlex":         {"replacement": "tJavaRow",      "auto_fix": False, "risk": "HIGH"},
}

# -------------------------------------------------------
# RISK RULES (kept for legacy analyzer)
# -------------------------------------------------------

COMPONENT_RISK_RULES = {
    "tJava": {
        "risk": "HIGH",
        "issue": "Custom Java Code",
        "recommendation": "Requires manual remediation"
    },
    "tSystem": {
        "risk": "CRITICAL",
        "issue": "OS Command Execution",
        "recommendation": "Replace with cloud-compatible service"
    },
    "tLibraryLoad": {
        "risk": "HIGH",
        "issue": "External Library Dependency",
        "recommendation": "Validate cloud runtime compatibility"
    },
    "tRunJob": {
        "risk": "MEDIUM",
        "issue": "Child Job Dependency",
        "recommendation": "Validate orchestration migration"
    },
    "tFileInputExcel": {
        "risk": "LOW",
        "issue": "Excel Processing",
        "recommendation": "Cloud supported"
    },
    "tBeanShell": {
        "risk": "HIGH",
        "issue": "Deprecated scripting component",
        "recommendation": "Replace with tJavaRow"
    },
}

# -------------------------------------------------------
# AUTO-FIX RECOMMENDATION RULES
# -------------------------------------------------------

AUTO_FIX_RULES = {
    "tMysqlInput":       "Convert to tDBInput with driver=MySQL",
    "tMysqlOutput":      "Convert to tDBOutput with driver=MySQL",
    "tOracleInput":      "Convert to tDBInput with driver=Oracle",
    "tOracleOutput":     "Convert to tDBOutput with driver=Oracle",
    "tMSSqlInput":       "Convert to tDBInput with driver=MSSQL",
    "tMSSqlOutput":      "Convert to tDBOutput with driver=MSSQL",
    "tBeanShell":        "Rewrite logic in tJavaRow",
    "tSystem":           "Replace with cloud function / REST call",
}
