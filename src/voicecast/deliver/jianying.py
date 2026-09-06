"""剪映交付包：批量配音结果 → 可直接导入剪映的成品包。

包含：
- SRT 字幕（每句音频时长已知 → 按集累计时间轴 + 句间间隔）
- 分轨说明（音频已按 E{ep}/{文件} 组织，剪映按目录/命名拖入）
- README 导入指引

剪映使用：导入 SRT 后字幕自动对齐时间轴；音频按命名（E01_S01_角色_003）
识别角色分轨管理。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.settings import REPO_ROOT

GAP_SEC = 0.3  # 句间间隔（字幕衔接留白）


def _duration_ms(wav: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(wav)],
        check=True, capture_output=True, text=True,
    )
    return int(float(out.stdout.strip()) * 1000)


def _ts(ms: int) -> str:
    """毫秒 → SRT 时间戳 00:00:00,000"""
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(records: list[dict], out_root: Path) -> list[Path]:
    """按集生成 SRT：句序累计时间轴（每句时长 + GAP）。返回生成的 srt 路径列表。"""
    srt_files: list[Path] = []
    by_ep: dict[int, list[dict]] = {}
    for r in records:
        if r.get("status") != "ok" or not r.get("file"):
            continue
        by_ep.setdefault(r.get("episode", 1), []).append(r)

    for ep in sorted(by_ep):
        lines = by_ep[ep]
        cursor = 0
        blocks: list[str] = []
        for i, r in enumerate(lines, 1):
            wav = out_root / r["file"]
            dur = _duration_ms(wav) if wav.exists() else 1500
            blocks.append(
                f"{i}\n{_ts(cursor)} --> {_ts(cursor + dur)}\n{r.get('role', '')}：{r.get('text', '')}\n"
            )
            cursor += dur + int(GAP_SEC * 1000)
        srt = out_root / f"E{ep:02d}/E{ep:02d}_字幕.srt"
        srt.write_text("\n".join(blocks) + "\n", encoding="utf-8-sig")
        srt_files.append(srt)
    return srt_files


def export_deliver(records: list[dict], out_root: Path, title: str = "配音成品") -> Path:
    """生成剪映交付包（在原输出目录旁）。返回 deliver 目录路径。"""
    out_root = Path(out_root)
    deliver = out_root.parent / f"{out_root.name}_剪映包"
    deliver.mkdir(parents=True, exist_ok=True)

    # 音频已就位 → 生成 SRT
    srt_files = build_srt(records, out_root)

    # README 导入指引
    readme = deliver / "导入说明.txt"
    role_files = sorted({r["file"].split("/")[-1] for r in records if r.get("file")})
    readme.write_text(
        f"【VoiceCast 剪映导入包】{title}\n"
        "==============================\n"
        "1. 音频文件在上一级输出目录，按 E{集}/E{集}_{场景}_{角色}_{句号}.wav 命名——\n"
        "   剪映导入后按角色名分轨管理，跨集角色名一致。\n"
        "2. 字幕文件 E*_字幕.srt 已与音频时间轴对齐（每句起始=集内累计时长），\n"
        "   剪映「文本→智能字幕→导入字幕」选择对应 srt 即可。\n"
        "3. 句间留白 0.3s；如需微调，剪映时间轴直接拖动即可。\n"
        "------------------------------\n"
        f"字幕文件：{len(srt_files)} 个\n"
        f"音频句数：{len([r for r in records if r.get('status') == 'ok'])} 句\n"
        f"角色文件示例：\n" + "\n".join(f"  {f}" for f in role_files[:8]) + "\n",
        encoding="utf-8",
    )
    # 复制 srt 进 deliver 方便一键导入
    for s in srt_files:
        (deliver / s.name).write_bytes(s.read_bytes())
    return deliver
