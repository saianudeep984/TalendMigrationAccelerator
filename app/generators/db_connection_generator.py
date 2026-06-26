"""
DB Connection Generator — Talend Open Studio → Talend 8

Generates Talend 8 native database connection metadata.
"""

import uuid
from datetime import datetime

TALEND8_PRODUCT = "8.0.1"
TALEND8_PRODUCT_FULL = "Talend Studio"


def _now_ms():
    return str(int(datetime.utcnow().timestamp() * 1000))


def _new_id():
    return "_" + uuid.uuid4().hex[:20].upper()


class DBConnectionGenerator:

    # DB type mapping Open Studio → Talend 8
    DB_TYPE_MAP = {
        "MySQL": "MYSQL",
        "Oracle": "ORACLE",
        "SQLServer": "MSSQL",
        "PostgreSQL": "POSTGRESQL",
        "DB2": "AS400",
        "Sybase": "SYBASE",
        "JDBC": "JDBC",
        "SQLite": "SQLITE",
        "Teradata": "TERADATA",
    }

    def generate(self, source_connection):
        """
        source_connection dict expected keys:
            name, db_type, host, port, db_name, user, password,
            schema, url, driver_class
        Returns:
            {item_xml, properties_xml, name}
        """
        name = source_connection.get("name", "DBConnection")
        db_type = self.DB_TYPE_MAP.get(
            source_connection.get("db_type", "JDBC"), "JDBC"
        )
        host = source_connection.get("host", "localhost")
        port = source_connection.get("port", "")
        db_name = source_connection.get("db_name", "")
        user = source_connection.get("user", "")
        password = source_connection.get("password", "")
        schema = source_connection.get("schema", "")
        url = source_connection.get("url", "")
        driver = source_connection.get("driver_class", "")
        created = _now_ms()
        conn_id = _new_id()
        prop_id = _new_id()
        state_id = _new_id()
        item_id = _new_id()

        item_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
  xmlns:metadata.connection="metadata.connection"
  xmlns:metadata.connection.impl="metadata.connection.impl">
  <metadata.connection:DatabaseConnection
    xmi:id="{conn_id}"
    databaseType="{db_type}"
    dbmsId="{db_type}"
    name="{name}"
    hostName="{host}"
    port="{port}"
    SID="{db_name}"
    username="{user}"
    password="{password}"
    schema="{schema}"
    URL="{url}"
    driverClass="{driver}"
    label="{name}"
    version="0.1"
    status=""/>
</xmi:XMI>
'''

        properties_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
  xmlns:org.talend.core.model.properties="org.talend.core.model.properties">
  <org.talend.core.model.properties:DatabaseConnectionItem
    xmi:id="{item_id}"
    description=""
    displayName="{name}"
    name="{name}"
    statusCode=""
    version="0.1"
    connection="{conn_id}"
    state="{state_id}">
    <property
      xmi:id="{prop_id}"
      author=""
      comment=""
      created="{created}"
      createdProductFullname="{TALEND8_PRODUCT_FULL}"
      createdProductVersion="{TALEND8_PRODUCT}"
      displayName="{name}"
      label="{name}"
      modified="{created}"
      modifiedProductFullname="{TALEND8_PRODUCT_FULL}"
      modifiedProductVersion="{TALEND8_PRODUCT}"
      purpose=""
      statusCode=""
      version="0.1"/>
  </org.talend.core.model.properties:DatabaseConnectionItem>
  <ItemState xmi:id="{state_id}" path=""/>
</xmi:XMI>
'''

        return {
            "version": "0.1",
            "name": name,
            "item_xml": item_xml.encode("utf-8"),
            "properties_xml": properties_xml.encode("utf-8"),
        }
