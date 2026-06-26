from lxml import etree as ET

from app.config.version_matrix import (
    VERSION_UPGRADE_MATRIX
)


class TalendVersionConverter:

    # ==================================================
    # INITIALIZATION
    # ==================================================

    def __init__(self):

        self.rules = VERSION_UPGRADE_MATRIX["7_to_8"]

        self.logs = []

        self.warnings = []

    # ==================================================
    # MAIN CONVERSION METHOD
    # ==================================================

    def convert(self, xml_content):

        try:

            parser = ET.XMLParser(
                recover=True,
                encoding="utf-8",
                resolve_entities=False,
                no_network=True
            )

            root = ET.fromstring(
                xml_content,
                parser
            )

            # -----------------------------------------
            # ONLY MODIFY JOB COMPONENT NODES
            # -----------------------------------------

            root = self.rename_components(root)

            root = self.detect_removed_components(root)

            root = self.fix_parameters(root)

            root = self.add_required_parameters(root)

            # -----------------------------------------
            # SAFE COMMENT ONLY
            # -----------------------------------------

            root = self.add_migration_metadata(root)

            # -----------------------------------------
            # FIX: Use unicode string output then
            # manually prepend the correct XML
            # declaration that Talend expects:
            # double quotes, uppercase UTF-8
            # lxml's xml_declaration=True produces
            # single quotes + lowercase which breaks
            # Talend Studio XML import
            # -----------------------------------------

            xml_body = ET.tostring(

                root,

                pretty_print=True,

                encoding="unicode"
            )

            xml_declaration = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
            )

            return (xml_declaration + xml_body).encode(
                "utf-8"
            )

        except Exception as e:

            self.warnings.append(

                f"Conversion failed: {str(e)}"
            )

            return xml_content

    # ==================================================
    # SAFE NODE FILTER
    # ==================================================

    def get_component_nodes(self, root):

        component_nodes = []

        for node in root.findall(".//node"):

            component_name = node.attrib.get(
                "componentName"
            )

            if component_name:

                component_nodes.append(node)

        return component_nodes

    # ==================================================
    # PHASE 3
    # COMPONENT RENAMING
    # ==================================================

    def rename_components(self, root):

        rename_rules = self.rules[
            "renamed_components"
        ]

        for node in self.get_component_nodes(root):

            component = node.attrib.get(
                "componentName"
            )

            if component in rename_rules:

                new_name = rename_rules[
                    component
                ]

                node.attrib[
                    "componentName"
                ] = new_name

                self.logs.append(

                    f"Renamed: "
                    f"{component} -> {new_name}"
                )

        return root

    # ==================================================
    # PHASE 4
    # REMOVED COMPONENT DETECTION
    # ==================================================

    def detect_removed_components(self, root):

        removed_components = self.rules[
            "removed_components"
        ]

        for node in self.get_component_nodes(root):

            component = node.attrib.get(
                "componentName"
            )

            if component in removed_components:

                # FIX: Do NOT add any unknown XML
                # elements to the node. Talend Studio
                # validates the XML schema on import
                # and rejects any unrecognised element
                # like <migrationWarning>. Just log
                # the warning — no XML mutation.

                self.warnings.append(

                    f"{component} is not "
                    f"supported in Talend 8"
                )

        return root

    # ==================================================
    # PHASE 5
    # PARAMETER CONVERSION
    # ==================================================

    def fix_parameters(self, root):

        parameter_rules = self.rules[
            "parameter_changes"
        ]

        for node in self.get_component_nodes(root):

            component = node.attrib.get(
                "componentName"
            )

            if component not in parameter_rules:

                continue

            rule = parameter_rules[
                component
            ]

            old_param = rule["OLD_PARAM"]

            new_param = rule["NEW_PARAM"]

            for param in node.findall(
                ".//elementParameter"
            ):

                param_name = param.attrib.get(
                    "name"
                )

                if param_name == old_param:

                    param.attrib[
                        "name"
                    ] = new_param

                    self.logs.append(

                        f"{component}: "
                        f"{old_param} "
                        f"-> "
                        f"{new_param}"
                    )

        return root

    # ==================================================
    # PHASE 6
    # ADD REQUIRED PARAMETERS
    # ==================================================

    def add_required_parameters(self, root):

        required_rules = self.rules[
            "new_required_parameters"
        ]

        for node in self.get_component_nodes(root):

            component = node.attrib.get(
                "componentName"
            )

            if component not in required_rules:

                continue

            existing_params = {

                param.attrib.get("name")

                for param in node.findall(
                    ".//elementParameter"
                )
            }

            required_params = required_rules[
                component
            ]

            for required_param in required_params:

                if required_param in existing_params:

                    continue

                new_param = ET.SubElement(

                    node,

                    "elementParameter"
                )

                # FIX: Use "CHECK" field type for
                # boolean params like TRUNCATE_TABLE.
                # "TODO" is not a valid Talend value
                # — use "false" as a safe default so
                # Talend Studio can parse the param.

                param_defaults = {
                    "TRUNCATE_TABLE": ("CHECK", "false"),
                }

                field_type, default_value = (
                    param_defaults.get(
                        required_param,
                        ("TEXT", "")
                    )
                )

                new_param.attrib["field"] = field_type

                new_param.attrib["name"] = (
                    required_param
                )

                new_param.attrib["value"] = (
                    default_value
                )

                self.logs.append(

                    f"Added parameter "
                    f"{required_param} "
                    f"to {component}"
                )

        return root

    # ==================================================
    # SAFE MIGRATION COMMENT
    # ==================================================

    def add_migration_metadata(self, root):

        try:

            comment = ET.Comment(

                "Converted by Talend "
                "Migration Accelerator"
            )

            root.insert(0, comment)

        except Exception:

            pass

        return root

    # ==================================================
    # GET LOGS
    # ==================================================

    def get_logs(self):

        return self.logs

    # ==================================================
    # GET WARNINGS
    # ==================================================

    def get_warnings(self):

        return self.warnings