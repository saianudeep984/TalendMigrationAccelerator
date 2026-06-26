
from lxml import etree as ET


class EMFIdExtractor:

    def extract_ids(self, content):

        ids = {}

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

                return ids

            for elem in root.iter():

                for key, value in elem.attrib.items():

                    if "id" in key.lower():
                        ids[key] = value

        except Exception as e:

            print(
                f"ID extraction failed: {str(e)}"
            )

        return ids
