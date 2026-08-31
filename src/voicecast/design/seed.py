"""种子音色库生成（可编程调用 + CLI）。

edge-tts 8 个中文音色 → 标准参考音频 → recipes/samples/seed/<voice>.wav
这些种子是本地引擎零样本克隆的底声，让"凭空设计"全程零外部依赖。
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import edge_tts

from ..core.settings import SEED_DIR

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


async def _gen_one(voice: str, out_wav: Path) -> Path:
    mp3 = out_wav.with_suffix(".mp3")
    await edge_tts.Communicate(REF_TEXT, voice, rate="+0%", volume="+0%").save(str(mp3))
    if has_ffmpeg():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1",
             "-acodec", "pcm_s16le", str(out_wav)],
            check=True, capture_output=True,
        )
        mp3.unlink(missing_ok=True)
    else:
        mp3.rename(out_wav)
    return out_wav


def generate_seed_library(out_dir: Path | None = None) -> list[Path]:
    out_dir = out_dir or SEED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    results = asyncio.run(
        asyncio.gather(*[_gen_one(v, out_dir / f"{v}.wav") for v in VOICES])
    )
    return list(results)
