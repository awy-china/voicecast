"""edge-tts 引擎：微软免费接口，零 key、零注册。默认兜底主干。

配方参数单位（edge-tts 约定）：
- base_voice: zh-CN-*Neural 音色 ID
- pitch: Hz（负值降调，实测 < -30Hz 失真，路由有质量门槛）
- speed: 倍率（1.0 原速，0.85 = -15%）
- volume: 倍率（1.0 原音量）
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from ..core.models import VoiceProfile, VoicecastError
from .base import Engine
from .util import verify_audio


class EdgeTTSEngine(Engine):
    name = "edge_tts"
    display_name = "edge-tts（微软，免费零 key）"

    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def synthesize(
        self, text: str, profile: VoiceProfile, out_path: Path, emotion: str = ""
    ) -> Path:
        import edge_tts

        out_path.parent.mkdir(parents=True, exist_ok=True)
        p = profile.params
        base = p.get("base_voice")
        if not base:
            raise VoicecastError(f"edge-tts 配方缺少 base_voice: {profile.id}")

        speed = float(p.get("speed", 1.0))
        pitch = float(p.get("pitch", 0))
        vol = float(p.get("volume", 1.0))
        rate = f"{(speed - 1) * 100:+.0f}%"
        pch = f"{pitch:+.0f}Hz"
        volume = f"{(vol - 1) * 100:+.0f}%"

        mp3 = out_path.with_suffix(".mp3")
        asyncio.run(
            edge_tts.Communicate(text, base, rate=rate, pitch=pch, volume=volume).save(
                str(mp3)
            )
        )
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(mp3), "-ar", "24000", "-ac", "1",
                 "-acodec", "pcm_s16le", str(out_path)],
                check=True, capture_output=True, timeout=60,
            )
        finally:
            mp3.unlink(missing_ok=True)

        v = verify_audio(out_path)
        if not v["ok"]:
            raise VoicecastError(f"edge-tts 输出校验失败: {profile.id} {v['reason']}")
        return out_path

    def explain(self) -> str:
        return f"{self.display_name}（免费，需联网）"
