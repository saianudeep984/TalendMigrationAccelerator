"""
Internal route registry.

Maps a route name to the callable that serves it. Used by the UI layer
(and any future HTTP wrapper) to look up service functions by name
instead of importing each one directly.
"""

from app.api.healthcheck import check_prerequisites
from app.api.migration_api import (
    get_replacement_recommendations,
    get_remediation_recommendations,
    get_upgrade_path_result,
    get_upgrade_path_results,
)

ROUTES = {
    "healthcheck": check_prerequisites,
    "replacement_recommendations": get_replacement_recommendations,
    "remediation_recommendations": get_remediation_recommendations,
    "upgrade_path_result": get_upgrade_path_result,
    "upgrade_path_results": get_upgrade_path_results,
}


def call_route(name: str, *args, **kwargs):
    if name not in ROUTES:
        raise KeyError(f"Unknown route: {name}")
    return ROUTES[name](*args, **kwargs)
