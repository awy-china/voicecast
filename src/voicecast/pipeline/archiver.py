"""归档：规范命名 + 按集/角色组织 + 元数据总表（CSV/JSON）。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..core.io import save_json


def line_filename(episode: int, scene: str, role_id: str, line_no: int) -> str:
    """E01_S02_duan_ye_003.wav（集_场_角色_序号）。"""
    scene_num = "".join(ch for ch in scene if ch.isdigit()) or "00"
    return f"E{episode:02d}_S{int(scene_num):02d}_{role_id}_{line_no:03d}.wav"


def write_manifest(records: list[dict], output_dir: Path) -> Path:
    """写 manifest.json + manifest.csv（每句的引擎/配方/成本/溯源）。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "manifest.json"
    save_json({"records": records}, json_path)

    csv_path = output_dir / "manifest.csv"
    if records:
        fields: list[str] = []
        for r in records:
            for k in r:
                if k not in fields:
                    fields.append(k)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(records)
    return json_path
