"""参考库增强：为每个说话人生成 3-10s 拼接参考（GPT-SoVITS 要求）。

背景：AISHELL-3 单段约 2-3s，短于 GPT-SoVITS 的 3-10s 要求。
处理：把每说话人的多段拼接成 1 段 *_ref.wav（含 0.25s 静音间隔），
文本同步拼接；更新 ref_voices_aishell3.yaml 的 ref_file 指向拼接版。
F5-TTS 无时长限制，拼接版对其同样可用（参考更长质量更好）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REF_DIR = REPO / "recipes" / "samples" / "ref"
RECIPE = REPO / "recipes" / "ref_voices_aishell3.yaml"

MIN_SEC, MAX_SEC = 3.0, 10.0
GAP_SEC = 0.25


def duration(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def concat(parts: list[Path], out: Path) -> None:
    inputs = []
    for p in parts:
        inputs += ["-i", str(p)]
    # 每段后补静音，再整体 concat
    filters = [f"[{i}:a]apad=pad_dur={GAP_SEC}[a{i}]" for i in range(len(parts))]
    ins = "".join(f"[a{i}]" for i in range(len(parts)))
    filters.append(f"{ins}concat=n={len(parts)}:v=0:a=1")
    subprocess.run(
        ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filters),
         "-ar", "24000", "-ac", "1", str(out)],
        check=True, capture_output=True,
    )


def main() -> None:
    import yaml

    recipe = yaml.safe_load(RECIPE.read_text(encoding="utf-8"))
    updated = 0
    for prof in recipe["profiles"]:
        rid: str = prof["id"]                      # aishell3_SSBxxxx
        sid = rid.removeprefix("aishell3_")
        segs = sorted(REF_DIR.glob(f"aishell3_{sid}_*.wav"))
        segs = [s for s in segs if "_ref.wav" not in s.name]
        if not segs:
            continue
        # 贪心拼接：凑够 >=3s（最多 4 段，控制 <=10s）
        chosen: list[Path] = []
        total = 0.0
        for s in segs:
            d = duration(s)
            if total + d + (GAP_SEC if chosen else 0) > MAX_SEC:
                continue
            chosen.append(s)
            total += d + (GAP_SEC if len(chosen) > 1 else 0)
            if total >= MIN_SEC:
                break
        if len(chosen) < 2:
            print(f"  ⚠️ {sid}: 段不足，跳过")
            continue
        ref_wav = REF_DIR / f"aishell3_{sid}_ref.wav"
        concat(chosen, ref_wav)
        texts = []
        for s in chosen:
            t = s.with_suffix(".txt")
            if t.exists():
                texts.append(t.read_text(encoding="utf-8").strip())
        (REF_DIR / f"aishell3_{sid}_ref.txt").write_text(
            "。".join(texts), encoding="utf-8")
        # 更新配方 ref_file
        prof["params"]["ref_file"] = f"samples/ref/aishell3_{sid}_ref.wav"
        prof["params"].pop("ref_text", None)
        updated += 1
        print(f"  ✅ {sid}: {len(chosen)} 段 → {total:.1f}s")

    RECIPE.write_text(
        "# 参考音频配方（自动生成：prepare_aishell3.py + build_gptsovits_refs.py）\n"
        "# 数据源 AISHELL-3（Apache-2.0）。ref 指向 3-10s 拼接参考（GPT-SoVITS 兼容）。\n"
        "# wav 本体不入 git（.gitignore）；ref_text 自动读 samples/ref/<同名>.txt。\n"
        + yaml.safe_dump(recipe, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\n完成：更新 {updated} 条配方 → {RECIPE}")


if __name__ == "__main__":
    sys.exit(main())
