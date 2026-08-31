"""JSON/YAML 读写与配方库加载。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import VoiceProfile, VoicecastError
from .settings import RECIPES_DIR


def load_yaml(path: Path | str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(data: Any, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def load_json(path: Path | str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_recipe_library() -> dict[str, VoiceProfile]:
    """加载通用配方库（recipes/voice_profiles.yaml），返回 id -> VoiceProfile。"""
    candidates = [
        RECIPES_DIR / "voice_profiles.yaml",
        RECIPES_DIR / "voice_profiles.json",
    ]
    for c in candidates:
        if c.exists():
            raw = load_yaml(c) if c.suffix == ".yaml" else load_json(c)
            items = raw.get("profiles", raw) if isinstance(raw, dict) else raw
            profiles: dict[str, VoiceProfile] = {}
            for item in items:
                p = VoiceProfile.model_validate(item)
                profiles[p.id] = p
            return profiles
    raise VoicecastError(f"配方库不存在: {RECIPES_DIR / 'voice_profiles.yaml'}")
