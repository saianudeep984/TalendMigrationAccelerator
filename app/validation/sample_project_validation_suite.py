"""
SampleProjectValidationSuite  (F9.6)

Validates ProjectClassifier detection accuracy and
TargetVersionRecommendationEngine recommendation accuracy against a
ground-truth fixture set covering Open Studio and Enterprise sample
projects on the Talend 7.x -> 8.x path.
"""

import tempfile
import zipfile
from typing import Any, Dict, List

from app.parser.project_classifier import ProjectClassifier, ProjectType
from app.analyzers.target_version_recommendation_engine import recommend_target_version


def _talend_project_xml(product_version: str, storage_type: str = "") -> str:
    storage_attr = f' storageType="{storage_type}"' if storage_type else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xmi:XMI xmlns:TalendProperties="http://www.talend.org/properties">\n'
        f'  <TalendProperties:Project productVersion="{product_version}"{storage_attr} language="java">\n'
        "  </TalendProperties:Project>\n"
        "</xmi:XMI>\n"
    )


SAMPLE_PROJECT_FIXTURES: List[Dict[str, Any]] = [
    {
        "name": "open_studio_7_3",
        "product_version": "Talend Open Studio for Data Integration-7.3.1",
        "storage_type": "local",
        "expected_project_type": ProjectType.OPEN_STUDIO,
        "expected_source_version": "Talend 7",
        "component_usage": [],
        "enterprise_features": {},
        "expected_target_version": "Talend 8",
    },
    {
        "name": "open_studio_7_with_removed_component",
        "product_version": "Talend Open Studio for Big Data-7.0.1",
        "storage_type": "local",
        "expected_project_type": ProjectType.OPEN_STUDIO,
        "expected_source_version": "Talend 7",
        "component_usage": ["tJavaFlex"],
        "enterprise_features": {},
        "expected_target_version": "Talend 8",
    },
    {
        "name": "enterprise_7_3",
        "product_version": "Talend Data Integration-7.3.1",
        "storage_type": "remote",
        "expected_project_type": ProjectType.ENTERPRISE,
        "expected_source_version": "Talend 7",
        "component_usage": [],
        "enterprise_features": {},
        "expected_target_version": "Talend 8",
    },
    {
        "name": "enterprise_7_4_with_mdm",
        "product_version": "Talend MDM-7.4.0",
        "storage_type": "remote",
        "expected_project_type": ProjectType.ENTERPRISE,
        "expected_source_version": "Talend 7",
        "component_usage": [],
        "enterprise_features": {"summary": ["MDM"]},
        "expected_target_version": "Talend Cloud",
    },
]


def _build_fixture_zip(fixture: Dict[str, Any], tmp_dir: str) -> str:
    path = f"{tmp_dir}/{fixture['name']}.zip"
    xml = _talend_project_xml(fixture["product_version"], fixture["storage_type"])
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("project/talend.project", xml)
    return path


def run_validation_suite(fixtures: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run detection + recommendation checks across all fixtures.

    Returns a report dict with per-fixture results and overall accuracy
    scores (0.0 - 1.0) for both detection and recommendation.
    """
    fixtures = fixtures if fixtures is not None else SAMPLE_PROJECT_FIXTURES
    classifier = ProjectClassifier()
    results = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for fixture in fixtures:
            zip_path = _build_fixture_zip(fixture, tmp_dir)
            classification = classifier.classify_zip(zip_path)

            detection_ok = (
                classification.project_type == fixture["expected_project_type"]
                and classification.version == fixture["expected_source_version"]
            )

            recommendation = recommend_target_version(
                classification.version,
                component_usage=fixture["component_usage"],
                enterprise_features=fixture["enterprise_features"],
            )
            recommendation_ok = (
                recommendation["supported"]
                and recommendation["recommendedTarget"] == fixture["expected_target_version"]
            )

            results.append({
                "name": fixture["name"],
                "detected_project_type": classification.project_type.value,
                "detected_source_version": classification.version,
                "detection_passed": detection_ok,
                "recommended_target": recommendation["recommendedTarget"],
                "recommendation_passed": recommendation_ok,
            })

    total = len(results) or 1
    detection_accuracy = sum(1 for r in results if r["detection_passed"]) / total
    recommendation_accuracy = sum(1 for r in results if r["recommendation_passed"]) / total

    return {
        "results": results,
        "detection_accuracy": detection_accuracy,
        "recommendation_accuracy": recommendation_accuracy,
    }
