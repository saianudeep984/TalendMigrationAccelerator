from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Optional


@dataclass(frozen=True)
class LazyModule:
    module_path: str
    callable_name: str = "render"


class LazyLoader:
    """Dynamic import helper for page and tab payloads."""

    def __init__(self) -> None:
        self._modules: Dict[str, Any] = {}

    def import_module(self, module_path: str) -> Any:
        if module_path not in self._modules:
            self._modules[module_path] = importlib.import_module(module_path)
        return self._modules[module_path]

    def resolve(self, module_path: str, callable_name: str = "render") -> Callable[..., Any]:
        module = self.import_module(module_path)
        return getattr(module, callable_name)

    def call(self, module_path: str, callable_name: str = "render", *args: Any, **kwargs: Any) -> Any:
        return self.resolve(module_path, callable_name)(*args, **kwargs)

    def loaded_modules(self) -> list[str]:
        return sorted(self._modules)


class LazyTabRegistry:
    """Executes only the active tab payload."""

    def __init__(self, session: Optional[Dict[str, Any]] = None) -> None:
        self.session = session if session is not None else {}
        self._tabs: Dict[str, Callable[[], Any]] = {}

    def register(self, key: str, renderer: Callable[[], Any]) -> None:
        self._tabs[key] = renderer

    def active_key(self, group_key: str, default: Optional[str] = None) -> Optional[str]:
        if group_key not in self.session:
            self.session[group_key] = default or next(iter(self._tabs), None)
        return self.session.get(group_key)

    def render_active(self, group_key: str, active: Optional[str] = None, default: Optional[str] = None) -> Any:
        key = active or self.active_key(group_key, default)
        if key not in self._tabs:
            return None
        self.session[group_key] = key
        return self._tabs[key]()

    def keys(self) -> list[str]:
        return list(self._tabs)


def lazy_tabs(
    group_key: str,
    tabs: Dict[str, Callable[[], Any]] | Iterable[tuple[str, Callable[[], Any]]],
    active: Optional[str] = None,
    session: Optional[Dict[str, Any]] = None,
) -> Any:
    registry = LazyTabRegistry(session)
    for key, renderer in dict(tabs).items():
        registry.register(key, renderer)
    return registry.render_active(group_key, active)


def lazy_value(active: bool, loader: Callable[[], Any], placeholder: Optional[Callable[[], Any]] = None) -> Any:
    if active:
        return loader()
    if placeholder:
        return placeholder()
    return None
