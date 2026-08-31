#!/usr/bin/env python
"""种子音色库生成：edge-tts 8 个中文音色 → 标准参考音频（本地引擎克隆底声）。

输出：recipes/samples/seed/<voice_id>.wav（24kHz 单声道）
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import edge_tts

from voicecast.core.settings import SEED_DIR

# 标准参考文本：中性、有停顿/转折/情绪起伏（实测：平铺直叙的底声 → 念稿感）
REF_TEXT = (
    "我站在老槐树下，望着远处的山。风很大，吹得衣角猎猎作响。"
    "这些年走过许多地方，见过许多人，可最忘不了的，还是故乡那条小河。"
    "河水清亮，映着天光，哗啦啦地响。小时候总觉得日子过不完，"
    "如今回头看，一晃就是半生。人这一辈子啊，说长也长，说短也短，"
    "要紧的是，心里始终有光。"
)

VOICES = [
    "zh-CN-YunxiNeural",
    "zh-CN-YunxiaNeural",
    "zh-CN-YunjianNeural",
    "zh-CN-YunyangNeural",
    "zh-CN-XiaoxiaoNeural",
    "zh-CN-XiaoyiNeural",
    "zh-CN-liaoning-XiaobeiNeural",
    "zh-CN-shaanxi-XiaoniNeural",
]


def has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


async def gen_one(voice: str, out_wav: Path) -> None:
    mp3 = out_wav.with_suffix(".mp3")
    await edge_tts.Communicate(REF_TEXT, voice, rate="+0%", volume="+0%").save(str(mp3))
    if has_ffmpeg():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1",
             "-acodec", "pcm_s16le", str(out_wav)],
            check=True, capture_output=True,
        )
        mp3.unlink()
    else:
        mp3.rename(out_wav)  # 无 ffmpeg 时保留 mp3 兜底
    size_mb = out_wav.stat().st_size / 1024 / 1024
    print(f"[seed] {out_wav.name}  {size_mb:.1f}MB")


async def main() -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    for v in VOICES:
        await gen_one(v, SEED_DIR / f"{v}.wav")
    print(f"\n种子音色库完成：{SEED_DIR}")


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    asyncio.run(main())
