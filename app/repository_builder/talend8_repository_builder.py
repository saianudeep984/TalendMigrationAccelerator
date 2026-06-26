"""
Talend 8 Repository Builder — v3 (Project Skeleton Fix)

Root cause from Phase 9/10 analysis:
  - Generated talend.project used wrong namespace (org.talend.core.model.properties)
    instead of the required TalendProperties namespace
  - Missing .project (Eclipse project descriptor) — Talend cannot register the project
  - Missing skeleton folders: TDQ_Libraries, Databases, Maps, Reports,
    Structures, sqlPatterns, documentations

Fix strategy (v3):
  Mode A — Skeleton ZIP provided (RECOMMENDED):
    Copy ALL files from MIGRATIONTEMPLATE skeleton ZIP verbatim,
    then OVERLAY only: context/, metadata/, process/, code/
    This guarantees Talend sees a valid registered project.

  Mode B — No skeleton ZIP:
    Generate .project and talend.project with CORRECT TalendProperties namespace
    and create all required empty skeleton folders so Talend can register the project.

Full pipeline:
  1. Parse source Open Studio ZIP
  2. Extract jobs, contexts, routines, file-metadata
  3. Lay down skeleton (Mode A or B)
  4. Generate Talend 8 native artifacts over skeleton
  5. Apply context XMI ID consistency check
  6. Package into migrated_repository.zip (no pycache / temp files)

Import into Talend 8 Studio:
  File → Import → Talend Items → select the ZIP → tick all → Finish
"""

import os
import zipfile
import tempfile
import shutil
import uuid
import re
from datetime import datetime

from app.utils.zip_extractor import safe_extract
from app.parser.talend_xml_parser import TalendJobParser
from app.cache.cache_manager import CacheManager as _CacheManager
from app.parser.repository_scanner import find_talend_jobs
from app.generators.context_generator import ContextGenerator
from app.generators.db_connection_generator import DBConnectionGenerator
from app.generators.job_generator import JobGenerator
from app.generators.routine_generator import RoutineGenerator
from app.generators.file_metadata_generator import FileMetadataGenerator
from app.emf.context_item_state_fixer import (
    fix_context_properties_in_dir,
    remove_invalid_xml_references_in_dir,
)


# ---------------------------------------------------------------------------
# FIXED: Use TalendProperties namespace (not org.talend.core.model.properties)
# This is the namespace that real Talend 8 projects use in talend.project
# ---------------------------------------------------------------------------
TALEND_PROJECT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI"
  xmlns:TalendProperties="http://www.talend.org/properties">
  <TalendProperties:Project
    xmi:id="_{uid}"
    name="{name}"
    label="{name}"
    description="Migrated from Talend Open Studio to Talend 8"
    language="JAVA"
    productVersion="8.0.1"
    creationDate="{created}"
    lastModificationDate="{created}"
    technicalLabel="{name}"
    author="_MIGRATION_AUTHOR"/>
  <TalendProperties:User
    xmi:id="_MIGRATION_AUTHOR"
    login="migration@talend.com"
    password="D41D8CD98F00B204E9800998ECF8427E"/>
</xmi:XMI>
"""

# ---------------------------------------------------------------------------
# FIXED: .project Eclipse descriptor — REQUIRED for Talend project registration
# Without this file Talend Studio silently ignores the project folder
# ---------------------------------------------------------------------------
ECLIPSE_DOT_PROJECT_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
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

# Directories that must NOT appear in the output ZIP
_EXCLUDE_DIRS = {".metadata", "imported_repository", "__pycache__", ".git"}
_EXCLUDE_EXTS = {".pyc", ".pyo"}

# Artifact folders we OVERLAY on top of the skeleton (never copy from skeleton for these)
_OVERLAY_DIRS = {"context", "metadata", "process", "code"}

# Required empty skeleton folders that Talend expects to exist
_REQUIRED_SKELETON_FOLDERS = [
    "context",
    "metadata/connections",
    "metadata/fileExcel",
    "metadata/fileDelimited",
    "metadata/genericSchema",
    "process",
    "process/Standard",
    "code/routines",
    ".settings",
    # Phase 8 discovery — Talend requires these folders to register project
    "TDQ_Libraries",
    "Databases",
    "Maps",
    "Reports",
    "Structures",
    "sqlPatterns",
    "documentations",
]


class Talend8RepositoryBuilder:

    def __init__(self):
        self.context_gen = ContextGenerator()
        self.db_gen = DBConnectionGenerator()
        self.job_gen = JobGenerator()
        self.routine_gen = RoutineGenerator()
        self.file_meta_gen = FileMetadataGenerator()
        self.log = []
        self.stats = {
            "jobs_generated": 0,
            "contexts_generated": 0,
            "connections_generated": 0,
            "routines_generated": 0,
            "file_metadata_generated": 0,
            "errors": [],
        }

    def build_from_zip(
        self,
        source_zip_path,
        output_zip_path,
        project_name="MigratedProject",
        skeleton_zip_path=None,
    ):
        """
        Full pipeline: source ZIP → Talend 8 ZIP.

        skeleton_zip_path (optional): path to a MIGRATIONTEMPLATE ZIP.
            If provided, all skeleton files are copied verbatim and only
            context/metadata/process/code are overlaid with generated content.
            This is the recommended mode for guaranteed project registration.
        """
        # Sanitize project name (no spaces, no special chars)
        project_name = (
            project_name.strip()
            .replace(" ", "_")
            .replace("&", "_")
            .replace("<", "_")
            .replace(">", "_")
        )
        if not project_name:
            project_name = "MigratedProject"

        work_dir = tempfile.mkdtemp(prefix="talend8_build_")
        try:
            extract_dir = os.path.join(work_dir, "source")
            repo_dir = os.path.join(work_dir, "repo", project_name)

            self._log("Extracting source ZIP")
            os.makedirs(extract_dir, exist_ok=True)
            safe_extract(source_zip_path, extract_dir)

            # ------------------------------------------------------------------
            # PHASE A: lay down skeleton
            # ------------------------------------------------------------------
            if skeleton_zip_path and os.path.isfile(skeleton_zip_path):
                self._log("Mode A: copying skeleton from MIGRATIONTEMPLATE ZIP")
                self._apply_skeleton_zip(skeleton_zip_path, repo_dir, project_name)
            else:
                self._log("Mode B: generating project skeleton (no template ZIP provided)")
                self._build_folder_structure(repo_dir)
                self._write_project_file(repo_dir, project_name)
                self._write_eclipse_dot_project(repo_dir, project_name)
                self._write_settings(repo_dir, project_name)

            # ------------------------------------------------------------------
            # PHASE B: overlay native Talend artifacts
            # ------------------------------------------------------------------
            self._log("Copying native Talend artifacts")
            source_root = self._find_source_project_root(extract_dir)
            if source_root:
                self._overlay_source_artifacts(source_root, repo_dir)
            else:
                self._log("No native project root found - using reconstruction fallback")
                self._reconstruct_source_artifacts(extract_dir, repo_dir)

            self._log("Removing illegal XML character references")
            xml_fixes = remove_invalid_xml_references_in_dir(repo_dir)
            if xml_fixes:
                self._log(f"Sanitized {len(xml_fixes)} XML item file(s)")

            # Post-generation: ensure context XMI IDs are consistent
            self._log("Verifying context XMI ID consistency")
            ctx_dir = os.path.join(repo_dir, "context")
            if os.path.isdir(ctx_dir):
                fixes = fix_context_properties_in_dir(ctx_dir)
                if fixes:
                    self._log(f"Applied {len(fixes)} context XMI ID fix(es)")

            self._log("Packaging output ZIP")
            self._package_zip(os.path.join(work_dir, "repo"), output_zip_path)
            self._log("Build complete ✓")

            return {
                "success": True,
                "stats": self.stats,
                "log": self.log,
                "output_zip": output_zip_path,
            }

        except Exception as e:
            self._log(f"FATAL ERROR: {e}")
            self.stats["errors"].append(str(e))
            return {
                "success": False,
                "stats": self.stats,
                "log": self.log,
                "error": str(e),
            }
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # SKELETON METHODS
    # ------------------------------------------------------------------

    def _find_source_project_root(self, extract_root):
        """Find the exported project root that owns the Talend artifact folders."""
        candidates = []

        for root, dirs, files in os.walk(extract_root):
            dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
            artifact_dirs = sum(name in dirs for name in _OVERLAY_DIRS)
            if artifact_dirs == 0:
                continue
            candidates.append((
                "talend.project" in files,
                artifact_dirs,
                -root.count(os.sep),
                root,
            ))

        if not candidates:
            return None

        return max(candidates)[-1]

    def _overlay_source_artifacts(self, source_root, repo_dir):
        """Copy native Talend artifacts without flattening paths or rebuilding XMI."""
        counts = {
            "jobs_generated": 0,
            "contexts_generated": 0,
            "connections_generated": 0,
            "routines_generated": 0,
            "file_metadata_generated": 0,
        }

        for overlay_dir in sorted(_OVERLAY_DIRS):
            src = os.path.join(source_root, overlay_dir)
            if not os.path.isdir(src):
                continue

            dst = os.path.join(repo_dir, overlay_dir)
            shutil.copytree(src, dst, dirs_exist_ok=True)
            self._rewrite_author_links_in_dir(dst)

            for root, _, files in os.walk(dst):
                item_files = [fname for fname in files if fname.endswith(".item")]
                rel_root = os.path.relpath(root, repo_dir).replace("\\", "/")

                if rel_root == "process" or rel_root.startswith("process/"):
                    counts["jobs_generated"] += len(item_files)
                elif rel_root == "context" or rel_root.startswith("context/"):
                    counts["contexts_generated"] += len(item_files)
                elif rel_root == "metadata/connections" or rel_root.startswith("metadata/connections/"):
                    counts["connections_generated"] += len(item_files)
                elif rel_root == "code/routines" or rel_root.startswith("code/routines/"):
                    counts["routines_generated"] += len(item_files)
                elif rel_root == "metadata" or rel_root.startswith("metadata/"):
                    counts["file_metadata_generated"] += len(item_files)

        for key, value in counts.items():
            self.stats[key] += value

        self._log(
            "Native overlay copied: "
            f"{counts['jobs_generated']} job(s), "
            f"{counts['contexts_generated']} context(s), "
            f"{counts['connections_generated']} connection(s), "
            f"{counts['routines_generated']} routine(s), "
            f"{counts['file_metadata_generated']} other metadata item(s)"
        )

    def _rewrite_author_links_in_dir(self, root_dir):
        """Point copied properties files at the migration user in the target project."""
        for root, _, files in os.walk(root_dir):
            for fname in files:
                if not fname.endswith(".properties"):
                    continue

                path = os.path.join(root, fname)
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()

                fixed_content = re.sub(
                    r'(<author\s+href="[^"]*talend\.project#)[^"]+(")',
                    r'\1_MIGRATION_AUTHOR\2',
                    content,
                )
                if fixed_content == content:
                    continue

                with open(path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)

    def _reconstruct_source_artifacts(self, extract_dir, repo_dir):
        """Fallback for archives without a discoverable native project root."""
        self._log("Scanning for jobs")
        job_files = find_talend_jobs(extract_dir)
        self._log(f"Found {len(job_files)} job file(s)")
        for jf in job_files:
            self._process_job(jf, repo_dir)

        self._process_contexts(extract_dir, repo_dir)
        self._process_db_connections(extract_dir, repo_dir)
        self._process_routines(extract_dir, repo_dir)
        self._process_file_metadata(extract_dir, repo_dir)

    def _apply_skeleton_zip(self, skeleton_zip_path, repo_dir, project_name):
        """
        Mode A: extract skeleton ZIP, copy all files EXCEPT overlay dirs,
        then patch talend.project and .project with the new project name.
        """
        skel_tmp = tempfile.mkdtemp(prefix="talend8_skel_")
        try:
            safe_extract(skeleton_zip_path, skel_tmp)

            # Find the root project folder inside the skeleton ZIP
            skel_root = self._find_project_root(skel_tmp)
            if not skel_root:
                self._log("Warning: could not detect skeleton root — using zip root")
                skel_root = skel_tmp

            os.makedirs(repo_dir, exist_ok=True)

            # Copy everything except overlay dirs
            for item in os.listdir(skel_root):
                if item in _OVERLAY_DIRS:
                    continue  # will be generated later
                src = os.path.join(skel_root, item)
                dst = os.path.join(repo_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

            # Create empty overlay dirs so generators can write into them
            for folder in _REQUIRED_SKELETON_FOLDERS:
                os.makedirs(os.path.join(repo_dir, folder), exist_ok=True)

            # Patch talend.project with new name (keep skeleton structure, replace name only)
            self._patch_or_write_project_file(repo_dir, project_name)
            self._patch_or_write_eclipse_dot_project(repo_dir, project_name)
            self._write_settings(repo_dir, project_name)

            self._log(f"Skeleton applied from template. Project name patched to: {project_name}")

        finally:
            shutil.rmtree(skel_tmp, ignore_errors=True)

    def _find_project_root(self, extract_root):
        """
        Heuristic: the skeleton project root is the first subfolder that
        contains 'talend.project' or '.project'.
        """
        # Check direct children first
        for entry in os.listdir(extract_root):
            candidate = os.path.join(extract_root, entry)
            if os.path.isdir(candidate):
                contents = os.listdir(candidate)
                if "talend.project" in contents or ".project" in contents:
                    return candidate
        # Fallback: check root itself
        root_contents = os.listdir(extract_root)
        if "talend.project" in root_contents or ".project" in root_contents:
            return extract_root
        return None

    def _patch_or_write_project_file(self, repo_dir, project_name):
        """
        If talend.project exists from skeleton, patch name/technicalLabel in-place.
        Otherwise write from template with CORRECT TalendProperties namespace.
        """
        tp = os.path.join(repo_dir, "talend.project")
        if os.path.isfile(tp):
            with open(tp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Patch only the project element. Other labels in talend.project
            # belong to statuses and component settings.
            def patch_project_element(match):
                project_element = match.group(0)
                for attr in ("name", "label", "technicalLabel"):
                    project_element = re.sub(
                        rf'(?<={attr}=")[^"]*',
                        project_name,
                        project_element,
                    )
                return project_element

            content = re.sub(
                r"<TalendProperties:Project\b[^>]*>",
                patch_project_element,
                content,
                count=1,
            )
            if 'xmi:id="_MIGRATION_AUTHOR"' not in content:
                migration_author = (
                    '  <TalendProperties:User xmi:id="_MIGRATION_AUTHOR" '
                    'login="migration@talend.com" '
                    'password="D41D8CD98F00B204E9800998ECF8427E"/>\n'
                )
                content = content.replace("</xmi:XMI>", migration_author + "</xmi:XMI>")
            with open(tp, "w", encoding="utf-8") as f:
                f.write(content)
            self._log(f"Patched talend.project name → {project_name}")
        else:
            self._write_project_file(repo_dir, project_name)

    def _patch_or_write_eclipse_dot_project(self, repo_dir, project_name):
        """
        If .project exists from skeleton, patch <name> in-place.
        Otherwise write from template.
        """
        dp = os.path.join(repo_dir, ".project")
        if os.path.isfile(dp):
            with open(dp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            content = re.sub(r'<name>[^<]*</name>', f'<name>{project_name}</name>', content)
            with open(dp, "w", encoding="utf-8") as f:
                f.write(content)
            self._log(f"Patched .project name → {project_name}")
        else:
            self._write_eclipse_dot_project(repo_dir, project_name)

    # ------------------------------------------------------------------
    # MODE B: generate skeleton from scratch
    # ------------------------------------------------------------------

    def _build_folder_structure(self, repo_dir):
        for folder in _REQUIRED_SKELETON_FOLDERS:
            os.makedirs(os.path.join(repo_dir, folder), exist_ok=True)

    def _write_project_file(self, repo_dir, project_name):
        """Write talend.project with CORRECT TalendProperties namespace."""
        created = str(int(datetime.utcnow().timestamp() * 1000))
        uid = uuid.uuid4().hex[:20].upper()
        content = TALEND_PROJECT_TEMPLATE.format(
            uid=uid, name=project_name, created=created
        )
        with open(os.path.join(repo_dir, "talend.project"), "w", encoding="utf-8") as f:
            f.write(content)

    def _write_eclipse_dot_project(self, repo_dir, project_name):
        """Write .project Eclipse descriptor — REQUIRED for Talend project registration."""
        content = ECLIPSE_DOT_PROJECT_TEMPLATE.format(name=project_name)
        with open(os.path.join(repo_dir, ".project"), "w", encoding="utf-8") as f:
            f.write(content)

    def _write_settings(self, repo_dir, project_name):
        settings_dir = os.path.join(repo_dir, ".settings")
        os.makedirs(settings_dir, exist_ok=True)
        prefs = (
            "eclipse.preferences.version=1\n"
            f"projectName={project_name}\n"
            "talend.version=8.0.1\n"
        )
        with open(
            os.path.join(settings_dir, "org.talend.designer.core.prefs"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(prefs)

    # ------------------------------------------------------------------
    # JOB / CONTEXT / ROUTINE / METADATA PROCESSING (unchanged)
    # ------------------------------------------------------------------

    def _process_job(self, job_file, repo_dir):
        try:
            parser = TalendJobParser(job_file)
            job_name = parser.get_job_name()
            job_version = parser.get_job_version()
            if not job_name:
                return

            # PASS-THROUGH: copy original .item bytes directly.
            # The source .item already has all component parameters, positions,
            # schemas, connections. Re-generating loses all of that.
            # We only regenerate .properties (must be Talend 8 format).
            with open(job_file, "rb") as fh:
                original_item_bytes = fh.read()

            props_result = self.job_gen.generate_properties_only(
                job_name=job_name,
                job_version=job_version,
            )

            result = {
                "name": job_name,
                "version": job_version,
                "item_xml": original_item_bytes,
                "properties_xml": props_result["properties_xml"],
            }

            self._write_artifact(os.path.join(repo_dir, "process"), result["name"], result)
            self.stats["jobs_generated"] += 1
            self._log(f"  Job: {job_name} v{job_version}")
        except Exception as e:
            err = f"Job error [{os.path.basename(job_file)}]: {e}"
            self._log(err)
            self.stats["errors"].append(err)

    def _process_contexts(self, extract_dir, repo_dir):
        ctx_out = os.path.join(repo_dir, "context")
        found = 0
        for root, dirs, files in os.walk(extract_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            if os.path.basename(root) == "context":
                for fname in files:
                    if not fname.endswith(".item"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        ctx_name = fname.replace(".item", "")
                        variables = self._extract_context_vars(fpath)
                        result = self.context_gen.generate(
                            {"name": ctx_name, "variables": variables}
                        )
                        self._write_artifact(ctx_out, ctx_name, result)
                        self.stats["contexts_generated"] += 1
                        found += 1
                        self._log(f"  Context: {ctx_name} ({len(variables)} var(s))")
                    except Exception as e:
                        self.stats["errors"].append(f"Context error [{fname}]: {e}")

        if found == 0:
            self._log("No contexts found — creating Default context placeholder")
            result = self.context_gen.generate(
                {
                    "name": "Default",
                    "variables": [
                        {
                            "name": "ENV",
                            "value": "DEV",
                            "type": "id_String",
                            "comment": "Environment (DEV/UAT/PROD)",
                        }
                    ],
                }
            )
            self._write_artifact(ctx_out, "Default", result)
            self.stats["contexts_generated"] += 1

    def _extract_context_vars(self, item_path):
        from lxml import etree as ET

        variables = []
        try:
            parser = ET.XMLParser(recover=True, encoding="utf-8", resolve_entities=False, no_network=True)
            tree = ET.parse(item_path, parser)
            root = tree.getroot()
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "contextParameter":
                    name = elem.attrib.get("name", "")
                    value = elem.attrib.get(
                        "value", elem.attrib.get("defaultValue", "")
                    )
                    vtype = elem.attrib.get(
                        "type", elem.attrib.get("talendType", "id_String")
                    )
                    comment = elem.attrib.get("comment", "")
                    if name:
                        variables.append(
                            {
                                "name": name,
                                "value": value,
                                "type": vtype,
                                "comment": comment,
                            }
                        )
        except Exception:
            pass
        return variables


    def _process_db_connections(self, extract_dir, repo_dir):
        """
        Scan source for metadata/connections/*.item files,
        parse each connection XML, and generate Talend 8 native connection artifacts.
        """
        conn_out = os.path.join(repo_dir, "metadata", "connections")
        found = 0

        for root, dirs, files in os.walk(extract_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            root_norm = root.replace("\\", "/")
            if "metadata" in root_norm and "connection" in root_norm.lower():
                for fname in files:
                    if not fname.endswith(".item"):
                        continue
                    fpath = os.path.join(root, fname)
                    try:
                        conn_data = self._extract_db_connection(fpath)
                        if not conn_data.get("name"):
                            continue
                        result = self.db_gen.generate(conn_data)
                        self._write_artifact(conn_out, conn_data["name"], result)
                        self.stats["connections_generated"] += 1
                        found += 1
                        self._log(
                            f"  DB Connection: {conn_data['name']} "
                            f"({conn_data.get('db_type', 'JDBC')})"
                        )
                    except Exception as e:
                        err = f"Connection error [{fname}]: {e}"
                        self._log(err)
                        self.stats["errors"].append(err)

        if found == 0:
            self._log("No DB connections found in metadata/connections/")

    def _extract_db_connection(self, item_path):
        """
        Parse a Talend connection .item file and return a dict
        compatible with DBConnectionGenerator.generate().
        Handles both attribute-style and child-element-style formats.
        """
        from lxml import etree as ET

        conn = {
            "name": "",
            "db_type": "JDBC",
            "host": "localhost",
            "port": "",
            "db_name": "",
            "user": "",
            "password": "",
            "schema": "",
            "url": "",
            "driver_class": "",
        }

        ATTR_MAP = {
            "databaseType": "db_type",
            "dbType":       "db_type",
            "dbmsId":       "db_type",
            "hostName":     "host",
            "host":         "host",
            "server":       "host",
            "port":         "port",
            "SID":          "db_name",
            "database":     "db_name",
            "dbName":       "db_name",
            "schema":       "schema",
            "username":     "user",
            "user":         "user",
            "login":        "user",
            "password":     "password",
            "URL":          "url",
            "url":          "url",
            "driverClass":  "driver_class",
        }

        try:
            parser = ET.XMLParser(recover=True, encoding="utf-8", resolve_entities=False, no_network=True)
            tree = ET.parse(item_path, parser)
            xml_root = tree.getroot()

            # Default name from filename
            base = os.path.basename(item_path).replace(".item", "")
            conn["name"] = base.replace("&","_").replace("<","_").replace(">","_")

            for elem in xml_root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

                # Match any element that looks like a connection node
                if "Connection" in tag or "connection" in tag.lower():
                    for attr_xml, attr_key in ATTR_MAP.items():
                        val = elem.attrib.get(attr_xml, "")
                        if val:
                            conn[attr_key] = val
                    # Use label or name attribute if present and meaningful
                    label = elem.attrib.get("label", elem.attrib.get("name", ""))
                    if label and label not in ("DatabaseConnection", base):
                        conn["name"] = label.replace("&","_").replace("<","_").replace(">","_")

                # Also match child element tags (e.g. <host>value</host>)
                for attr_xml, attr_key in ATTR_MAP.items():
                    if tag.lower() == attr_xml.lower() and elem.text and elem.text.strip():
                        if not conn[attr_key]:
                            conn[attr_key] = elem.text.strip()

        except Exception as e:
            self._log(f"  Warning: could not parse {os.path.basename(item_path)}: {e}")

        return conn

    def _process_routines(self, extract_dir, repo_dir):
        rtn_out = os.path.join(repo_dir, "code", "routines")
        for root, dirs, files in os.walk(extract_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            root_base = os.path.basename(root).lower()
            if "routine" in root_base or root_base == "code":
                for fname in files:
                    if fname.endswith(".item"):
                        fpath = os.path.join(root, fname)
                        try:
                            rtn_name = fname.replace(".item", "")
                            content = self._extract_routine_content(fpath)
                            result = self.routine_gen.generate(
                                {
                                    "name": rtn_name,
                                    "content": content,
                                    "package": "routines",
                                }
                            )
                            self._write_artifact(rtn_out, rtn_name, result)
                            self.stats["routines_generated"] += 1
                            self._log(f"  Routine: {rtn_name}")
                        except Exception as e:
                            self.stats["errors"].append(
                                f"Routine error [{fname}]: {e}"
                            )

    def _extract_routine_content(self, item_path):
        from lxml import etree as ET

        try:
            parser = ET.XMLParser(recover=True, encoding="utf-8", resolve_entities=False, no_network=True)
            tree = ET.parse(item_path, parser)
            root = tree.getroot()
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag in ("content", "sourceCode", "code") and elem.text:
                    return elem.text
        except Exception:
            pass
        name = os.path.basename(item_path).replace(".item", "")
        return (
            f"// Migrated: {name}\n"
            f"public class {name} {{\n"
            f"    // TODO: restore routine logic\n"
            f"}}"
        )

    def _process_file_metadata(self, extract_dir, repo_dir):
        for meta_type, out_subdir, kw in [
            ("excel", "metadata/fileExcel", "fileExcel"),
            ("delimited", "metadata/fileDelimited", "fileDelimited"),
        ]:
            meta_out = os.path.join(repo_dir, out_subdir)
            for root, dirs, files in os.walk(extract_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                if kw in root:
                    for fname in files:
                        if fname.endswith(".item"):
                            try:
                                meta_name = fname.replace(".item", "")
                                result = self.file_meta_gen.generate(
                                    {"name": meta_name, "file_type": meta_type}
                                )
                                self._write_artifact(meta_out, meta_name, result)
                                self.stats["file_metadata_generated"] += 1
                                self._log(f"  File metadata: {meta_name}")
                            except Exception as e:
                                self.stats["errors"].append(
                                    f"Metadata error [{fname}]: {e}"
                                )

    def _write_artifact(self, output_dir, name, result):
        os.makedirs(output_dir, exist_ok=True)
        # Talend requires version suffix: JobName_0.1.item / JobName_0.1.properties
        version = result.get("version", "0.1")
        file_base = f"{name}_{version}"
        with open(os.path.join(output_dir, f"{file_base}.item"), "wb") as f:
            f.write(result["item_xml"])
        with open(os.path.join(output_dir, f"{file_base}.properties"), "wb") as f:
            f.write(result["properties_xml"])

    def _package_zip(self, source_dir, output_zip_path):
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for dirpath, dirnames, filenames in os.walk(source_dir):
                # Exclude unwanted dirs in-place
                dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
                for filename in filenames:
                    if os.path.splitext(filename)[1] in _EXCLUDE_EXTS:
                        continue
                    filepath = os.path.join(dirpath, filename)
                    arcname = os.path.relpath(filepath, source_dir)
                    zf.write(filepath, arcname)

    def _log(self, msg):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        self.log.append(f"[{ts}] {msg}")
