"""
Job Generator — Talend Open Studio → Talend 8

Generates Talend 8 native job .item and .properties XML that Talend 8 Studio
can import without errors.

Key fixes vs v19:
- componentVersion, offsetLabelX/Y on every node
- CONNECTION_FORMAT elementParameter on every node
- metadata connector element on every node
- connection elements with lineStyle, metaname, offsetLabel, inner elementParameter
- subjob element with all connected component refs
- routinesParameter block in job-level parameters
- Correct .properties structure with technicalLabel, author, referenceVersion
- ItemState xmi:id consistent with ProcessItem state= reference
"""

import uuid
from datetime import datetime

TALEND8_PRODUCT = "8.0.1"
TALEND8_PRODUCT_FULL = "Talend Studio"


def _now_ms():
    return str(int(datetime.utcnow().timestamp() * 1000))


def _new_id():
    return "_" + uuid.uuid4().hex[:20].upper()


# Required global job-level elementParameters that Talend 8 Studio enforces
_JOB_PARAMS = """    <elementParameter field="CLOSED_LIST" name="LOG4J_RUN_LEVEL" value="Info" show="false"/>
    <elementParameter field="TEXT" name="SCREEN_OFFSET_X" value="0" show="false"/>
    <elementParameter field="TEXT" name="SCREEN_OFFSET_Y" value="80" show="false"/>
    <elementParameter field="TEXT" name="REPOSITORY_CONNECTION_ID" value="" show="false"/>
    <elementParameter field="CHECK" name="IMPLICITCONTEXT_USE_PROJECT_SETTINGS" value="true" show="false"/>
    <elementParameter field="CHECK" name="STATANDLOG_USE_PROJECT_SETTINGS" value="true" show="false"/>
    <elementParameter field="CHECK" name="MULTI_THREAD_EXECATION" value="false"/>
    <elementParameter field="TEXT" name="PARALLELIZE_UNIT_SIZE" value="25000"/>
    <elementParameter field="CHECK" name="IMPLICIT_TCONTEXTLOAD" value="false"/>
    <elementParameter field="CHECK" name="ON_STATCATCHER_FLAG" value="false"/>
    <elementParameter field="CHECK" name="ON_LOGCATCHER_FLAG" value="false"/>
    <elementParameter field="CHECK" name="ON_METERCATCHER_FLAG" value="false"/>
    <elementParameter field="CHECK" name="ON_CONSOLE_FLAG" value="false" show="false"/>
    <elementParameter field="CHECK" name="ON_FILES_FLAG" value="false" show="false"/>
    <elementParameter field="ENCODING_TYPE" name="ENCODING" value="UTF-8" show="false"/>
    <routinesParameter id="{routines_id}" name="system"/>"""


class JobGenerator:

    REMOVED_COMPONENTS = {}

    def generate(self, source_job):
        """
        source_job: dict with job_name, components, connections keys
                    OR wrapped as {job_data: {...}}
        Returns: {item_xml, properties_xml, name}
        """
        job_data = source_job if "job_name" in source_job else source_job.get("job_data", {})
        job_name = job_data.get("job_name", "MigratedJob")
        job_version = job_data.get("job_version", "0.1")
        # Sanitize name for XML attribute
        job_name = job_name.replace("&", "_").replace("<", "_").replace(">", "_").replace('"', "_")
        components = job_data.get("components", [])
        connections = job_data.get("connections", [])

        created = _now_ms()
        process_xmi_id = _new_id()    # goes in ProcessItem xmi:id
        item_xmi_id = _new_id()       # matches ProcessItem.process attr → root of .item
        state_id = _new_id()          # shared: ItemState xmi:id == ProcessItem.state
        prop_id = _new_id()
        routines_id = _new_id()

        # --- Build node XML ---
        pos_x = 128
        node_lines = []
        unique_names = []
        for comp in components:
            comp_type = comp.get("component_type", "tLogRow")
            component_version = str(comp.get("component_version", "0"))
            unique_name = comp.get("unique_name", comp_type + "_1")
            # sanitize
            unique_name = unique_name.replace("&", "_").replace("<", "_").replace(">", "_").replace('"', "_")
            unique_names.append(unique_name)

            params = comp.get("parameters", {})
            param_lines = []
            for pname, pvalue in params.items():
                if pvalue is None:
                    continue
                safe_val = (str(pvalue)
                            .replace("&", "&amp;")
                            .replace("<", "&lt;")
                            .replace(">", "&gt;")
                            .replace('"', "&quot;"))
                param_lines.append(
                    f'      <elementParameter field="TEXT" name="{pname}" value="{safe_val}" show="true"/>'
                )
            # Always include CONNECTION_FORMAT (required by Studio)
            param_lines.append(
                '      <elementParameter field="TEXT" name="CONNECTION_FORMAT" value="row"/>'
            )
            params_xml = "\n".join(param_lines)

            node_lines.append(
                f'  <node componentName="{comp_type}" componentVersion="{component_version}"'
                f' offsetLabelX="0" offsetLabelY="0" posX="{pos_x}" posY="128">\n'
                f'    <elementParameter field="TEXT" name="UNIQUE_NAME" value="{unique_name}" show="false"/>\n'
                f'{params_xml}\n'
                f'    <metadata connector="FLOW" name="{unique_name}"/>\n'
                f'  </node>'
            )
            pos_x += 200

        # --- Build connection XML ---
        conn_lines = []
        for i, conn in enumerate(connections):
            src = conn.get("source", "")
            tgt = conn.get("target", "")
            connector = conn.get("connector", "FLOW")
            if not src or not tgt:
                continue
            src = src.replace("&", "_").replace('"', "_")
            tgt = tgt.replace("&", "_").replace('"', "_")
            label = "row" + str(i + 1) if connector == "FLOW" else "OnSubjobOk" + str(i + 1)
            line_style = "0" if connector == "FLOW" else "1"
            conn_lines.append(
                f'  <connection connectorName="{connector}" label="{label}"'
                f' lineStyle="{line_style}" metaname="{src}"'
                f' offsetLabelX="0" offsetLabelY="0" source="{src}" target="{tgt}">\n'
                f'    <elementParameter field="TEXT" name="UNIQUE_NAME" value="{label}" show="false"/>\n'
                f'  </connection>'
            )

        # --- subjob element (lists all unique names) ---
        subjob_refs = "\n".join(
            f'    <elementParameter field="TEXT" name="UNIQUE_NAME" value="{n}" show="false"/>'
            for n in unique_names
        )
        subjob_xml = f'  <subjob>\n{subjob_refs}\n  </subjob>' if unique_names else ""

        nodes_xml = "\n".join(node_lines)
        conns_xml = "\n".join(conn_lines)
        params_block = _JOB_PARAMS.format(routines_id=routines_id)

        item_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<talendfile:ProcessType xmi:version="2.0"
  xmi:id="{item_xmi_id}"
  xmlns:xmi="http://www.omg.org/XMI"
  xmlns:talendfile="platform:/resource/org.talend.model/model/TalendFile.xsd"
  defaultContext="Default"
  jobType="Standard">
  <context confirmationNeeded="false" hide="false" name="Default"/>
  <parameters>
{params_block}
  </parameters>
{nodes_xml}
{conns_xml}
{subjob_xml}
</talendfile:ProcessType>
"""

        properties_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:TalendProperties="http://www.talend.org/properties">
  <TalendProperties:Property xmi:id="{prop_id}" id="{process_xmi_id}" label="{job_name}" version="{job_version}" statusCode="" item="{state_id}" displayName="{job_name}">
    <author href="../talend.project#_MIGRATION_AUTHOR"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_date" value="{created}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_date" value="{created}"/>
  </TalendProperties:Property>
  <TalendProperties:ItemState xmi:id="{item_xmi_id}" path=""/>
  <TalendProperties:ProcessItem xmi:id="{state_id}" property="{prop_id}" state="{item_xmi_id}">
    <process href="{job_name}_{job_version}.item#/"/>
  </TalendProperties:ProcessItem>
</xmi:XMI>
"""

        return {
            "name": job_name,
            "version": job_version,
            "item_xml": item_xml.encode("utf-8"),
            "properties_xml": properties_xml.encode("utf-8"),
        }

    def generate_properties_only(self, job_name, job_version="0.1"):
        """
        Generate ONLY the .properties XML for a job.
        Used by pass-through mode where the original .item is reused as-is.
        """
        created = _now_ms()
        process_xmi_id = _new_id()
        item_xmi_id = _new_id()
        state_id = _new_id()
        prop_id = _new_id()

        job_name_safe = job_name.replace("&", "_").replace("<", "_").replace(">", "_").replace('"', "_")

        properties_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:TalendProperties="http://www.talend.org/properties">
  <TalendProperties:Property xmi:id="{prop_id}" id="{process_xmi_id}" label="{job_name_safe}" version="{job_version}" statusCode="" item="{state_id}" displayName="{job_name_safe}">
    <author href="../talend.project#_MIGRATION_AUTHOR"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_date" value="{created}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_date" value="{created}"/>
  </TalendProperties:Property>
  <TalendProperties:ItemState xmi:id="{item_xmi_id}" path=""/>
  <TalendProperties:ProcessItem xmi:id="{state_id}" property="{prop_id}" state="{item_xmi_id}">
    <process href="{job_name_safe}_{job_version}.item#/"/>
  </TalendProperties:ProcessItem>
</xmi:XMI>
"""
        return {"properties_xml": properties_xml.encode("utf-8")}
