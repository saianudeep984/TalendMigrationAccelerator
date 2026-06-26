"""
Tests for app.parser.project_classifier.ProjectClassifier

Covers:
  - Open Studio detection via productVersion
  - Enterprise detection via productVersion
  - Cloud detection via productVersion keyword
  - Cloud detection via structural marker file
  - Enterprise detection via storageType="remote"
  - Open Studio detection via storageType="local"
  - Structural fallback for .project/.settings
  - Unknown result when no markers present
  - Version extraction (Talend 6 / 7 / 8)
  - Bad ZIP returns UNKNOWN without raising
"""

import io
import zipfile

import pytest

from app.parser.project_classifier import ClassificationResult, ProjectClassifier, ProjectType


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_zip(members: dict[str, str], tmp_path, name="test.zip") -> str:
    """Write an in-memory ZIP to *tmp_path* and return its path string."""
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        for member_name, content in members.items():
            zf.writestr(member_name, content)
    return str(path)


def _talend_project_xml(product_version: str, storage_type: str = "", talend_ver: str = "7.3") -> str:
    storage_attr = f' storageType="{storage_type}"' if storage_type else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xmi:XMI xmlns:TalendProperties="http://www.talend.org/properties">\n'
        f'  <TalendProperties:Project productVersion="{product_version}"{storage_attr}'
        f' local="true" language="java">\n'
        f'    <!-- version hint: {talend_ver} -->\n'
        "  </TalendProperties:Project>\n"
        "</xmi:XMI>\n"
    )


# ── Open Studio ────────────────────────────────────────────────────────────────

class TestOpenStudio:
    def test_detect_via_product_version(self, tmp_path):
        pv = "Talend Open Studio for Data Integration-7.3.1"
        z = _make_zip({"project/talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.OPEN_STUDIO
        assert r.confidence == "HIGH"

    def test_version_extracted(self, tmp_path):
        pv = "Talend Open Studio for Big Data-6.5.0"
        z = _make_zip({"talend.project": _talend_project_xml(pv, talend_ver="6.5")}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.version == "Talend 6"

    def test_storage_local_fallback(self, tmp_path):
        xml = (
            '<TalendProperties:Project storageType="local" language="java">'
            "</TalendProperties:Project>"
        )
        z = _make_zip({"talend.project": xml}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.OPEN_STUDIO

    def test_product_version_string_stored(self, tmp_path):
        pv = "Talend Open Studio for Data Quality-8.0.0"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.product_version_string == pv


# ── Enterprise ─────────────────────────────────────────────────────────────────

class TestEnterprise:
    def test_detect_data_integration(self, tmp_path):
        pv = "Talend Data Integration-7.3.1"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.ENTERPRISE

    def test_detect_mdm(self, tmp_path):
        pv = "Talend MDM Platform-7.3.1"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.ENTERPRISE

    def test_storage_remote(self, tmp_path):
        xml = (
            '<TalendProperties:Project storageType="remote" language="java">'
            "</TalendProperties:Project>"
        )
        z = _make_zip({"talend.project": xml}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.ENTERPRISE

    def test_structural_eclipse_settings(self, tmp_path):
        """No talend.project; .project file present → Enterprise (LOW confidence)."""
        z = _make_zip(
            {
                ".project": "<projectDescription><name>MyProject</name></projectDescription>",
                "items/job1/job1_0.1.item": "<dummy/>",
            },
            tmp_path,
        )
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.ENTERPRISE
        assert r.confidence == "LOW"

    def test_version_extracted_enterprise(self, tmp_path):
        pv = "Talend Data Management Platform-8.0.0"
        z = _make_zip({"talend.project": _talend_project_xml(pv, talend_ver="8.0")}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.version == "Talend 8"


# ── Cloud ──────────────────────────────────────────────────────────────────────

class TestCloud:
    def test_detect_via_cloud_keyword(self, tmp_path):
        pv = "Talend Cloud Data Integration-8.0.1"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.CLOUD
        assert r.confidence == "HIGH"

    def test_detect_via_tiap_keyword(self, tmp_path):
        pv = "Talend TIAP-8.0.0"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.CLOUD

    def test_detect_via_remote_project_marker(self, tmp_path):
        """No talend.project; .remote_project file present → Cloud."""
        z = _make_zip(
            {
                ".remote_project": "projectId=abc123",
                "items/job1.item": "<dummy/>",
            },
            tmp_path,
        )
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.CLOUD
        assert r.confidence == "MEDIUM"

    def test_detect_via_manifest_yaml(self, tmp_path):
        z = _make_zip(
            {
                "manifest.yaml": "cloudProjectId: xyz789\nname: MyCloudProject\n",
                "items/job1.item": "<dummy/>",
            },
            tmp_path,
        )
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.CLOUD

    def test_data_fabric_keyword(self, tmp_path):
        pv = "Talend Data Fabric-8.0.0"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.CLOUD


# ── Unknown / edge cases ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_bad_zip_returns_unknown(self, tmp_path):
        bad = tmp_path / "bad.zip"
        bad.write_bytes(b"this is not a zip file")
        r = ProjectClassifier().classify_zip(str(bad))
        assert r.project_type == ProjectType.UNKNOWN
        assert any("Invalid ZIP" in s for s in r.signals)

    def test_no_markers_returns_unknown(self, tmp_path):
        z = _make_zip({"readme.txt": "nothing here"}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.UNKNOWN

    def test_to_dict(self, tmp_path):
        pv = "Talend Open Studio for Data Integration-7.3.1"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        d = r.to_dict()
        assert d["project_type"] == "Open Studio"
        assert "signals" in d
        assert isinstance(d["signals"], list)

    def test_signals_populated(self, tmp_path):
        pv = "Talend Open Studio for Data Integration-7.3.1"
        z = _make_zip({"talend.project": _talend_project_xml(pv)}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert len(r.signals) >= 1

    def test_version_unknown_when_absent(self, tmp_path):
        xml = '<TalendProperties:Project storageType="local"></TalendProperties:Project>'
        z = _make_zip({"talend.project": xml}, tmp_path)
        r = ProjectClassifier().classify_zip(z)
        assert r.version == "UNKNOWN"

    def test_nested_talend_project(self, tmp_path):
        """talend.project nested inside a folder hierarchy is still found."""
        pv = "Talend Open Studio for Data Integration-6.0.1"
        xml = _talend_project_xml(pv, talend_ver="6.0")
        z = _make_zip(
            {"project/items/sriyamlxigaapi/talend.project": xml},
            tmp_path,
        )
        r = ProjectClassifier().classify_zip(z)
        assert r.project_type == ProjectType.OPEN_STUDIO
        assert r.version == "Talend 6"

    def test_classify_extracted(self, tmp_path):
        """classify_extracted works on a directory."""
        pv = "Talend Data Integration-8.0.0"
        proj_dir = tmp_path / "project" / "items" / "myproj"
        proj_dir.mkdir(parents=True)
        (proj_dir / "talend.project").write_text(
            _talend_project_xml(pv, talend_ver="8.0"), encoding="utf-8"
        )
        r = ProjectClassifier().classify_extracted(str(tmp_path))
        assert r.project_type == ProjectType.ENTERPRISE
        assert r.version == "Talend 8"
