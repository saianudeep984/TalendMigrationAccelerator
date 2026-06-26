"""
Talend repository XML repair utility.

Repairs:
  1. Reconcile ItemState references inside context .properties files.
  2. Remove illegal XML 1.0 numeric character references from XML .item files.
"""

import os
import re
import shutil
import tempfile
import zipfile
from xml.sax.saxutils import escape

from app.utils.zip_extractor import safe_extract


_XML_CHAR_REF = re.compile(r"&#(?:x([0-9A-Fa-f]+)|([0-9]+));")
_ECLIPSE_PROJECT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<projectDescription>
  <name>{name}</name>
  <comment></comment>
  <projects>
  </projects>
  <buildSpec>
    <buildCommand>
      <name>org.eclipse.jdt.core.javabuilder</name>
      <arguments>
      </arguments>
    </buildCommand>
    <buildCommand>
      <name>org.talend.designer.core.builder</name>
      <arguments>
      </arguments>
    </buildCommand>
  </buildSpec>
  <natures>
    <nature>org.talend.designer.core.talendNature</nature>
    <nature>org.eclipse.jdt.core.javanature</nature>
  </natures>
</projectDescription>
"""


def _is_valid_xml_10_character(codepoint: int) -> bool:
    return (
        codepoint in (0x9, 0xA, 0xD)
        or 0x20 <= codepoint <= 0xD7FF
        or 0xE000 <= codepoint <= 0xFFFD
        or 0x10000 <= codepoint <= 0x10FFFF
    )


def remove_invalid_xml_references_in_dir(root_dir: str) -> list:
    """Remove XML 1.0-forbidden numeric references from XML .item files."""
    fixes = []

    for root, _, files in os.walk(root_dir):
        parts = root.split(os.sep)
        if "code" in parts and "routines" in parts:
            continue

        for fname in files:
            if not fname.endswith(".item"):
                continue

            path = os.path.join(root, fname)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            removed = []

            def replace_invalid_reference(match):
                codepoint = int(match.group(1), 16) if match.group(1) else int(match.group(2))
                if _is_valid_xml_10_character(codepoint):
                    return match.group(0)
                removed.append(match.group(0))
                return ""

            fixed_content = _XML_CHAR_REF.sub(replace_invalid_reference, content)
            if not removed:
                continue

            with open(path, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            fixes.append({
                "file": os.path.relpath(path, root_dir),
                "removed_references": len(removed),
                "references": sorted(set(removed)),
            })

    return fixes


def ensure_project_descriptors_in_dir(root_dir: str) -> list:
    """Add Eclipse registration files beside exported talend.project files."""
    fixes = []

    for root, _, files in os.walk(root_dir):
        if "talend.project" not in files:
            continue

        project_path = os.path.join(root, "talend.project")
        with open(project_path, "r", encoding="utf-8", errors="replace") as f:
            project_content = f.read()

        match = re.search(r'\btechnicalLabel="([^"]+)"', project_content)
        project_name = match.group(1) if match else os.path.basename(root)
        project_name = escape(project_name)

        created = []
        eclipse_project_path = os.path.join(root, ".project")
        if not os.path.isfile(eclipse_project_path):
            with open(eclipse_project_path, "w", encoding="utf-8") as f:
                f.write(_ECLIPSE_PROJECT_TEMPLATE.format(name=project_name))
            created.append(".project")

        settings_dir = os.path.join(root, ".settings")
        prefs_path = os.path.join(settings_dir, "org.talend.designer.core.prefs")
        if not os.path.isfile(prefs_path):
            os.makedirs(settings_dir, exist_ok=True)
            with open(prefs_path, "w", encoding="utf-8") as f:
                f.write(
                    "eclipse.preferences.version=1\n"
                    f"projectName={project_name}\n"
                )
            created.append(".settings/org.talend.designer.core.prefs")

        if created:
            fixes.append({
                "project": project_name,
                "path": os.path.relpath(root, root_dir),
                "created": created,
            })

    return fixes


def fix_context_properties_in_dir(context_dir: str) -> list:
    """Reconcile context ItemState references within .properties files."""
    fixes = []

    if not os.path.isdir(context_dir):
        return fixes

    for fname in sorted(os.listdir(context_dir)):
        if not fname.endswith(".properties"):
            continue

        props_path = os.path.join(context_dir, fname)
        try:
            with open(props_path, "r", encoding="utf-8", errors="replace") as f:
                props = f.read()
        except OSError:
            continue

        state_ids = re.findall(r'ItemState xmi:id="([^"]+)"', props)
        if not state_ids:
            continue

        state_id = state_ids[0]
        state_refs = re.findall(r'\bstate="([^"]+)"', props)
        if state_refs == [state_id]:
            continue

        fixed_props = props
        for old_ref in state_refs:
            fixed_props = fixed_props.replace(
                f'state="{old_ref}"',
                f'state="{state_id}"',
            )

        with open(props_path, "w", encoding="utf-8") as f:
            f.write(fixed_props)

        fixes.append({
            "file": fname,
            "state_id": state_id,
            "old_state_refs": state_refs,
        })

    return fixes


def fix_zip(input_zip_path: str, output_zip_path: str) -> dict:
    """Repair a Talend repository ZIP and write an import-ready copy."""
    temp_dir = tempfile.mkdtemp(prefix="talend_fix_")

    try:
        safe_extract(input_zip_path, temp_dir)

        xml_fixes = remove_invalid_xml_references_in_dir(temp_dir)
        descriptor_fixes = ensure_project_descriptors_in_dir(temp_dir)
        context_fixes = []

        for root, _, _ in os.walk(temp_dir):
            if os.path.basename(root) == "context":
                context_fixes.extend(fix_context_properties_in_dir(root))

        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _, filenames in os.walk(temp_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    arcname = os.path.relpath(filepath, temp_dir)
                    zf.write(filepath, arcname)

        return {
            "success": True,
            "fixes_applied": len(xml_fixes) + len(context_fixes) + len(descriptor_fixes),
            "fix_details": context_fixes,
            "xml_fixes_applied": len(xml_fixes),
            "xml_fix_details": xml_fixes,
            "context_fixes_applied": len(context_fixes),
            "descriptor_fixes_applied": len(descriptor_fixes),
            "descriptor_fix_details": descriptor_fixes,
            "output_path": output_zip_path,
        }

    except Exception as e:
        return {
            "success": False,
            "fixes_applied": 0,
            "fix_details": [],
            "xml_fixes_applied": 0,
            "xml_fix_details": [],
            "context_fixes_applied": 0,
            "descriptor_fixes_applied": 0,
            "descriptor_fix_details": [],
            "error": str(e),
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
