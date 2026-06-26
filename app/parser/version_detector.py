"""
version_detector.py
Thin wrapper around ProjectClassifier for backward-compatible API.
"""
from __future__ import annotations
from app.parser.project_classifier import ProjectClassifier, ProjectType


def detect_talend_version(repo_path: str) -> str:
    """Return 'Talend 6/7/8' or 'UNKNOWN'. Backward-compatible."""
    result = ProjectClassifier().classify_extracted(repo_path)
    return result.version


def detect_project_info(repo_path: str) -> dict:
    """Return full classification dict (version, project_type, confidence, signals)."""
    result = ProjectClassifier().classify_extracted(repo_path)
    return result.to_dict()
