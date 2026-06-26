"""
File Metadata Generator — Talend Open Studio → Talend 8

Key fixes vs v19:
- Correct FileMetadataItem (Excel/Delimited) xmi structure
- technicalLabel, referenceVersion added
- ItemState xmi:id consistent with FileMetadataItem.state
"""

import uuid
from datetime import datetime

TALEND8_PRODUCT = "8.0.1"
TALEND8_PRODUCT_FULL = "Talend Studio"


def _now_ms():
    return str(int(datetime.utcnow().timestamp() * 1000))


def _new_id():
    return "_" + uuid.uuid4().hex[:20].upper()


class FileMetadataGenerator:

    def generate(self, source_meta):
        """
        source_meta dict keys:
            name      - metadata item name
            file_type - 'excel' | 'delimited' | 'generic'
        Returns: {item_xml, properties_xml, name}
        """
        name = source_meta.get("name", "MigratedMetadata")
        name = name.replace("&", "_").replace("<", "_").replace(">", "_").replace('"', "_")
        file_type = source_meta.get("file_type", "delimited")
        created = _now_ms()
        meta_id = _new_id()
        item_xmi_id = _new_id()
        prop_id = _new_id()
        state_id = _new_id()

        if file_type == "excel":
            item_type_ns = "FileExcel"
            item_class = "org.talend.core.model.properties:FileExcelItem"
            item_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
  xmlns:metadata.fileExcel="metadata.fileExcel">
  <metadata.fileExcel:FileExcel
    xmi:id="{meta_id}"
    name="{name}"
    label="{name}"
    fileName=""
    headerRow="1"
    firstColumn="1"
    lastColumn="10"
    sheetName=""/>
</xmi:XMI>
"""
        else:
            item_class = "org.talend.core.model.properties:FileDelimitedItem"
            item_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
  xmlns:metadata.fileDelimited="metadata.fileDelimited">
  <metadata.fileDelimited:FileDelimited
    xmi:id="{meta_id}"
    name="{name}"
    label="{name}"
    fileName=""
    fieldSeparator=";"
    rowSeparator="\\n"
    header="1"
    footer="0"
    limit="-1"
    encoding="UTF-8"/>
</xmi:XMI>
"""

        properties_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
  xmlns:org.talend.core.model.properties="org.talend.core.model.properties">
  <{item_class}
    xmi:id="{item_xmi_id}"
    description=""
    displayName="{name}"
    name="{name}"
    technicalLabel="{name}"
    statusCode=""
    version="0.1"
    item="{meta_id}"
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
      referenceVersion=""
      statusCode=""
      version="0.1"/>
  </{item_class}>
  <ItemState xmi:id="{state_id}" path=""/>
</xmi:XMI>
"""

        return {
            "version": "0.1",
            "name": name,
            "item_xml": item_xml.encode("utf-8"),
            "properties_xml": properties_xml.encode("utf-8"),
        }
