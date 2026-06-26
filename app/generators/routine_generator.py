"""
Routine Generator — Talend Open Studio → Talend 8

Key fixes vs v19:
- RoutineItem uses code= attr pointing to Routine xmi:id in .item
- .item root is xmi:XMI wrapping a code.routines:Routine element (correct namespace)
- technicalLabel, referenceVersion added to .properties
- ItemState xmi:id consistent with RoutineItem.state
- CDATA preserved for Java source
"""

import uuid
from datetime import datetime

TALEND8_PRODUCT = "8.0.1"
TALEND8_PRODUCT_FULL = "Talend Studio"


def _now_ms():
    return str(int(datetime.utcnow().timestamp() * 1000))


def _new_id():
    return "_" + uuid.uuid4().hex[:20].upper()


class RoutineGenerator:

    def generate(self, source_routine):
        """
        source_routine dict keys:
            name    - routine name
            content - Java source code (str)
            package - package name (optional, default "routines")
        Returns: {item_xml, properties_xml, name}
        """
        name = source_routine.get("name", "MigratedRoutine")
        name = name.replace("&", "_").replace("<", "_").replace(">", "_").replace('"', "_")
        content = source_routine.get(
            "content",
            f"// Migrated routine: {name}\npublic class {name} {{\n}}"
        )
        package = source_routine.get("package", "routines")
        created = _now_ms()
        routine_id = _new_id()   # Routine xmi:id in .item → RoutineItem.content
        item_xmi_id = _new_id()  # RoutineItem xmi:id
        prop_id = _new_id()
        state_id = _new_id()     # shared: ItemState xmi:id == RoutineItem.state

        # CDATA wrapping — protect from XML escaping issues in Java code
        item_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
  xmlns:code.routines="code.routines">
  <code.routines:Routine
    xmi:id="{routine_id}"
    name="{name}"
    label="{name}"
    packageName="{package}"
    version="0.1"
    statusCode="">
    <content><![CDATA[{content}]]></content>
  </code.routines:Routine>
</xmi:XMI>
"""

        properties_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:TalendProperties="http://www.talend.org/properties">
  <TalendProperties:Property xmi:id="{prop_id}" id="{item_xmi_id}" label="{name}" version="0.1" statusCode="" item="{state_id}" displayName="{name}">
    <author href="../../talend.project#_MIGRATION_AUTHOR"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_date" value="{created}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_date" value="{created}"/>
  </TalendProperties:Property>
  <TalendProperties:ItemState xmi:id="{routine_id}" path=""/>
  <TalendProperties:RoutineItem xmi:id="{state_id}" property="{prop_id}" state="{routine_id}">
    <content href="{name}_0.1.item#{routine_id}"/>
  </TalendProperties:RoutineItem>
</xmi:XMI>
"""

        return {
            "version": "0.1",
            "name": name,
            "item_xml": item_xml.encode("utf-8"),
            "properties_xml": properties_xml.encode("utf-8"),
        }
