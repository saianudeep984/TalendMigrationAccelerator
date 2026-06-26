
from lxml import etree as ET


class ContextReferenceRebuilder:

    def rebuild(self, content):

        try:

            parser = ET.XMLParser(
                recover=True,
                resolve_entities=False,
                no_network=True
            )

            root = ET.fromstring(
                content,
                parser
            )

            if root is None:

                return content

            for elem in root.iter():

                href = elem.attrib.get(
                    "href"
                )

                if href and ".item#" not in href:

                    elem.attrib["href"] = (
                        href.replace(
                            ".item",
                            ".item#"
                        )
                    )

            return ET.tostring(

                root,

                pretty_print=True,

                encoding="utf-8",

                xml_declaration=True
            )

        except Exception:

            return content
