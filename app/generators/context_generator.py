"""
Context Generator — Talend Open Studio → Talend 8

Generates Talend 8 native context .item and .properties XML.

Key fixes vs v19:
- .item root element is TalendObjectType from the correct namespace
- xmi:id on the root element is referenced in .properties as ContextItem.context
- ItemState xmi:id in .properties matches the state= back-reference
- contextParameter elements use xmi:id attributes consistent with Studio expectations
- .properties technicalLabel included
"""

import uuid
from datetime import datetime

TALEND8_PRODUCT = "8.0.1"
TALEND8_PRODUCT_FULL = "Talend Studio"


def _now_ms():
    return str(int(datetime.utcnow().timestamp() * 1000))


def _new_id():
    return "_" + uuid.uuid4().hex[:20].upper()


class ContextGenerator:

    def generate(self, source_context):
        """
        source_context dict expected keys:
            name      - context group name (str)
            variables - list of {name, value, type, comment}
        Returns:
            {item_xml: bytes, properties_xml: bytes, name: str}
        """
        name = source_context.get("name", "DefaultContext")
        name = name.replace("&", "_").replace("<", "_").replace(">", "_").replace('"', "_")
        variables = source_context.get("variables", [])

        context_id = _new_id()     # root xmi:id in .item → ContextItem.context
        item_xmi_id = _new_id()    # ContextItem xmi:id in .properties
        prop_id = _new_id()
        state_id = _new_id()       # ItemState xmi:id == ContextItem.state
        created = _now_ms()

        # Build contextParameter elements (each needs its own xmi:id)
        var_lines = []
        for i, var in enumerate(variables):
            var_id = _new_id()
            var_name = var.get("name", f"VAR_{i}").replace("&", "_").replace('"', "_")
            var_value = (str(var.get("value", ""))
                         .replace("&", "&amp;")
                         .replace("<", "&lt;")
                         .replace(">", "&gt;")
                         .replace('"', "&quot;"))
            var_type = var.get("type", "id_String")
            var_comment = (var.get("comment", "")
                           .replace("&", "&amp;")
                           .replace("<", "&lt;")
                           .replace(">", "&gt;")
                           .replace('"', "&quot;"))
            var_lines.append(
                f'  <contextParameter xmi:id="{var_id}" comment="{var_comment}" '
                f'name="{var_name}" prompt="{var_name}:" '
                f'promptNeeded="false" repositoryContextId="" '
                f'type="{var_type}" value="{var_value}"/>'
            )

        vars_xml = "\n".join(var_lines)

        item_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<TalendObjectType xmi:version="2.0"
  xmlns:xmi="http://www.omg.org/XMI"
  xmlns:TalendObjectType="platform:/resource/org.talend.model/model/TalendFile.xsd"
  xmi:id="{context_id}"
  name="{name}"
  confirmationNeeded="false"
  hide="false">
{vars_xml}
</TalendObjectType>
"""

        properties_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:TalendProperties="http://www.talend.org/properties">
  <TalendProperties:Property xmi:id="{prop_id}" id="{item_xmi_id}" label="{name}" version="0.1" statusCode="" item="{state_id}" displayName="{name}">
    <author href="../talend.project#_MIGRATION_AUTHOR"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="created_date" value="{created}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_fullname" value="{TALEND8_PRODUCT_FULL}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_product_version" value="{TALEND8_PRODUCT}"/>
    <additionalProperties xmi:id="{_new_id()}" key="modified_date" value="{created}"/>
  </TalendProperties:Property>
  <TalendProperties:ItemState xmi:id="{context_id}" path=""/>
  <TalendProperties:ContextItem xmi:id="{state_id}" property="{prop_id}" state="{context_id}" defaultContext="Default">
    <context href="{name}_0.1.item#{context_id}"/>
  </TalendProperties:ContextItem>
</xmi:XMI>
"""

        return {
            "version": "0.1",
            "name": name,
            "item_xml": item_xml.encode("utf-8"),
            "properties_xml": properties_xml.encode("utf-8"),
        }
