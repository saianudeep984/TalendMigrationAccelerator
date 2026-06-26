"""
Startup prerequisites checker.

Verifies the environment before the Streamlit UI accepts any uploads.
Call check_prerequisites() once at app startup and surface the result
in the sidebar so users understand what is and isn't available.

Checks:
  - Python version >= 3.9
  - All required packages from requirements.txt are importable
  - Optional: Ollama reachable (enables LLM mode)
  - Optional: Talend Studio executable found at a user-supplied path
"""

import sys
import importlib
import json
import urllib.request
import urllib.error
from typing import TypedDict

from app.ai.llm_engine import OLLAMA_MODEL

REQUIRED_PACKAGES = [
    "streamlit",
    "pandas",
    "openpyxl",
    "xlsxwriter",
    "plotly",
    "reportlab",
    "lxml",
    "requests",
    "networkx",
    "pyvis",
]

OLLAMA_URL = "http://localhost:11434/api/tags"


class PrerequisiteResult(TypedDict):
    ok: bool
    python_ok: bool
    python_version: str
    missing_packages: list
    ollama_available: bool
    ollama_model: str
    ollama_models: list
    warnings: list
    errors: list


def check_prerequisites(talend_studio_path: str = "") -> PrerequisiteResult:
    warnings: list = []
    errors: list = []

    # --- Python version ---
    major, minor = sys.version_info.major, sys.version_info.minor
    python_ok = (major, minor) >= (3, 9)
    python_version = f"{major}.{minor}.{sys.version_info.micro}"
    if not python_ok:
        errors.append(
            f"Python 3.9+ required, found {python_version}. "
            "Upgrade Python before running the accelerator."
        )

    # --- Required packages ---
    missing: list = []
    for pkg in REQUIRED_PACKAGES:
        try:
            importlib.import_module(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        errors.append(
            f"Missing packages: {', '.join(missing)}. "
            "Run: pip install -r requirements.txt"
        )

    # --- Ollama (optional) ---
    ollama_available = False
    ollama_models = []
    try:
        req = urllib.request.Request(OLLAMA_URL, method="GET")
        with urllib.request.urlopen(req, timeout=2) as resp:
            ollama_available = resp.status == 200
            if ollama_available:
                payload = json.loads(resp.read().decode("utf-8"))
                ollama_models = [
                    model.get("name", "")
                    for model in payload.get("models", [])
                    if model.get("name")
                ]
    except Exception:
        warnings.append(
            "Ollama not detected at localhost:11434. "
            "AI recommendations will use the built-in rule engine. "
            "Install Ollama + qwen2.5-coder:3b to enable LLM mode."
        )

    # --- Talend Studio (optional, only checked when path provided) ---
    if talend_studio_path:
        import os
        if not os.path.isfile(talend_studio_path):
            warnings.append(
                f"Talend Studio executable not found at: {talend_studio_path}. "
                "CLI automation will be unavailable; use the manual import guide."
            )

    overall_ok = python_ok and len(missing) == 0

    return PrerequisiteResult(
        ok=overall_ok,
        python_ok=python_ok,
        python_version=python_version,
        missing_packages=missing,
        ollama_available=ollama_available,
        ollama_model=OLLAMA_MODEL,
        ollama_models=ollama_models,
        warnings=warnings,
        errors=errors,
    )
