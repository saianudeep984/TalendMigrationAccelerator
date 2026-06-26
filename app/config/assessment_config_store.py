import copy
import json
import os
from datetime import datetime


CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config"))
GLOBAL_PATH = os.path.join(CONFIG_DIR, "assessment_config.json")
PROJECT_PATH = os.path.join(CONFIG_DIR, "assessment_project_overrides.json")
AUDIT_PATH = os.path.join(CONFIG_DIR, "assessment_config_audit.jsonl")
HISTORY_DIR = os.path.join(CONFIG_DIR, "assessment_config_history")


DEFAULT_CONFIG = {
    "version": 1,
    "active_profile": "Enterprise",
    "profiles": ["Conservative", "Standard", "Enterprise", "Cloud First", "Custom"],
    "complexity": {
        "component_weight": 30,
        "sql_weight": 40,
        "dependency_weight": 15,
        "custom_code_weight": 20,
        "risk_weight": 10,
        "thresholds": {"low": 40, "medium": 80, "high": 120},
    },
    "risk": {
        "unsupported_components_penalty": 20,
        "custom_java_penalty": 15,
        "external_scripts_penalty": 10,
        "legacy_components_penalty": 15,
        "complex_dependency_penalty": 10,
        "thresholds": {"low": 25, "medium": 50, "high": 75},
        "flag_tjava": True,
        "flag_deprecated": True,
        "flag_creds": True,
        "flag_context": True,
    },
    "effort": {
        "hours_per_component": 0.5,
        "hours_per_sql_query": 1.0,
        "hours_per_dependency": 0.5,
        "hours_per_custom_code": 2.0,
    },
    "cloud": {
        "custom_java_usage": True,
        "file_system_dependency": True,
        "unsupported_components": True,
        "legacy_context_variables": True,
        "thresholds": {"ready": 80, "partially_ready": 50},
    },
}


def _ensure_dirs() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)


def _read_json(path: str, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(fallback)


def _write_json(path: str, data) -> None:
    _ensure_dirs()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_global_config() -> dict:
    data = _read_json(GLOBAL_PATH, DEFAULT_CONFIG)
    merged = copy.deepcopy(DEFAULT_CONFIG)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def load_project_overrides() -> dict:
    return _read_json(PROJECT_PATH, {})


def load_config(project_key: str | None = None) -> dict:
    config = load_global_config()
    if project_key:
        override = load_project_overrides().get(project_key)
        if isinstance(override, dict):
            for key, value in override.items():
                if isinstance(value, dict) and isinstance(config.get(key), dict):
                    config[key].update(value)
                else:
                    config[key] = value
            config["_project_override"] = project_key
    return config


def save_config(config: dict, actor: str = "streamlit", project_key: str | None = None) -> None:
    _ensure_dirs()
    payload = copy.deepcopy(config)
    payload["version"] = int(payload.get("version", 1)) + 1
    payload["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if project_key:
        overrides = load_project_overrides()
        overrides[project_key] = payload
        _write_json(PROJECT_PATH, overrides)
    else:
        _write_json(GLOBAL_PATH, payload)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    _write_json(os.path.join(HISTORY_DIR, f"assessment_config_v{payload['version']}_{stamp}.json"), payload)
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": payload["updated_at"],
            "actor": actor,
            "project_key": project_key or "global",
            "version": payload["version"],
            "active_profile": payload.get("active_profile"),
        }) + "\n")


def reset_defaults() -> dict:
    save_config(DEFAULT_CONFIG, actor="reset")
    return copy.deepcopy(DEFAULT_CONFIG)
