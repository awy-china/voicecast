"""剧本解析：txt 标记式（主格式）↔ JSON/JSONL（内部标准）。

txt 语法：
- 【角色】台词          → 一句台词（role=角色名）
- 【情绪】xxx           → 设置后续台词的默认情绪
- 【场景】S02 / # S02    → 设置后续台词的场景
- # 或 // 开头          → 注释
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Union

from ..core.io import load_json, save_json
from ..core.models import Script, ScriptLine, VoicecastError

ROLE_RE = re.compile(r"^【([^】]+)】(.*)$")
META_RE = re.compile(r"^【(情绪|场景|情绪:?)】\s*(.*)$", re.IGNORECASE)
SCENE_RE = re.compile(r"^#\s*S?(\d+)\s*$", re.IGNORECASE)


def parse_txt(text: str, title: str = "untitled") -> Script:
    lines: list[ScriptLine] = []
    emotion = "平静"
    scene = "S00"
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(("#", "//")):
            continue
        m = META_RE.match(line)
        if m:
            kind, val = m.group(1).lower(), m.group(2).strip()
            if "情绪" in kind:
                emotion = val or "平静"
            else:
                scene = val or "S00"
            continue
        m = SCENE_RE.match(line)
        if m:
            scene = f"S{int(m.group(1)):02d}"
            continue
        m = ROLE_RE.match(line)
        if not m:
            raise VoicecastError(f"第 {i} 行无法解析（应为【角色】台词）: {raw[:40]}")
        role, text = m.group(1).strip(), m.group(2).strip()
        if not text:
            continue
        lines.append(ScriptLine(
            role=role, text=text, emotion=emotion, scene=scene, line_no=len(lines) + 1,
        ))
    return Script(title=title, lines=lines)


def parse_file(path: Path | str) -> Script:
    path = Path(path)
    if path.suffix.lower() == ".json":
        data = load_json(path)
        return Script.model_validate(data)
    return parse_txt(path.read_text(encoding="utf-8"), title=path.stem)


def to_json(script: Script) -> dict:
    return script.model_dump()


def save_json_script(script: Script, path: Path | str) -> None:
    save_json(to_json(script), path)


def from_json_file(path: Path | str) -> Script:
    return Script.model_validate(load_json(path))


def to_txt(script: Script) -> str:
    """内部标准 → txt 标记式（可读可 diff，双向互转）。"""
    out: list[str] = []
    cur_emotion, cur_scene = "", ""
    for ln in script.lines:
        if ln.scene != cur_scene:
            out.append(f"【场景】{ln.scene}")
            cur_scene = ln.scene
        if ln.emotion != cur_emotion:
            out.append(f"【情绪】{ln.emotion}")
            cur_emotion = ln.emotion
        out.append(f"【{ln.role}】{ln.text}")
    return "\n".join(out) + "\n"
