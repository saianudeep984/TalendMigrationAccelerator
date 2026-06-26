import json
import os
from typing import Dict, Any


def _json_safe(value):
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return {
            "nodes": list(value.nodes()),
            "edges": [
                {"source": source, "target": target}
                for source, target in value.edges()
            ],
        }
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def export_dependency_summary(
    output_path: str,
    dependency_data: Dict[str, Any]
) -> str:
    """
    Export dependency summary to JSON file.

    Args:
        output_path (str): Directory to save the file
        dependency_data (Dict): Dependency analysis data

    Returns:
        str: Full path of generated JSON file
    """

    # Create output directory if it doesn't exist
    os.makedirs(output_path, exist_ok=True)

    file_path = os.path.join(
        output_path,
        "dependency_summary.json"
    )

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            _json_safe(dependency_data),
            f,
            indent=4,
            ensure_ascii=False,
            allow_nan=False
        )

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Exported JSON failed validation at {file_path}: {e}"
            ) from e

    return file_path
