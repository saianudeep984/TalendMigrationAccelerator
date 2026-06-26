import json
import os

_PROFILES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "ollama_profiles.json")

_DEFAULT_PROFILE = {
    "model": "qwen2.5-coder:3b",
    "temperature": 0.3,
    "top_p": 0.9,
    "max_tokens": 4096,
    "context_length": 8192,
    "system_prompt": "You are a Talend migration expert.",
}


class OllamaProfileStore:

    def _path(self) -> str:
        return os.path.abspath(_PROFILES_PATH)

    def load_all(self) -> dict:
        if os.path.exists(self._path()):
            try:
                with open(self._path(), "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"active": "default", "profiles": {"default": dict(_DEFAULT_PROFILE)}}

    def _save_all(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path()), exist_ok=True)
        with open(self._path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_active(self) -> dict:
        data = self.load_all()
        active = data.get("active", "default")
        return data["profiles"].get(active, dict(_DEFAULT_PROFILE))

    def save_profile(self, name: str, settings: dict) -> None:
        data = self.load_all()
        data["profiles"][name] = settings
        self._save_all(data)

    def delete_profile(self, name: str) -> None:
        data = self.load_all()
        if name == "default":
            return
        data["profiles"].pop(name, None)
        if data.get("active") == name:
            data["active"] = "default"
        self._save_all(data)

    def set_active(self, name: str) -> None:
        data = self.load_all()
        if name in data["profiles"]:
            data["active"] = name
            self._save_all(data)
