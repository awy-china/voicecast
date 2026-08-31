"""MiniMax 引擎：可选插件。无 MINIMAX_API_KEY 时 available()=False，路由自动跳过。

配方参数单位（MiniMax 约定）：
- base_voice: 预设音色 ID（female-shaonv / male-qn-qingse ...）或克隆 voice_id
- speed: 倍率（0.75~0.90 慢速=阴险/油腻，实测）
- pitch: -5~-3 低沉，-1~+2 明亮（与 edge-tts 的 Hz 单位不同！）
- volume: 倍率（1.0~1.2 加重气势）

踩坑处理（2026-08 实测）：audio 为 hex 字符串（非 base64）；克隆后必须立即验证（2054）；
Content-Type 用 httpx 天然正确（urllib 的 Request 构造后改 headers 无效）。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

from ..core.models import VoiceProfile, VoicecastError
from ..core.settings import OUTPUTS_DIR
from .base import Engine
from .util import verify_audio

API_URL = "https://api.minimaxi.com/v1/t2a_v2"
UPLOAD_URL = "https://api.minimaxi.com/v1/files/upload"
CLONE_URL = "https://api.minimaxi.com/v1/voice_clone"
MODEL = "speech-02-hd"


class MiniMaxEngine(Engine):
    name = "minimax"
    display_name = "MiniMax speech-02-hd（按量，可选插件）"

    def available(self) -> bool:
        return bool(os.environ.get("MINIMAX_API_KEY"))

    @property
    def cost_per_char(self) -> float:
        return 0.0001  # 粗略估算 1 元/万字（实际按量，记账为准）

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {os.environ['MINIMAX_API_KEY']}"}

    def synthesize(
        self, text: str, profile: VoiceProfile, out_path: Path, emotion: str = ""
    ) -> Path:
        if not self.available():
            raise VoicecastError("未配置 MINIMAX_API_KEY，路由不应选择本引擎")
        p = profile.params
        voice_id = p.get("base_voice")
        if not voice_id:
            raise VoicecastError(f"MiniMax 配方缺少 base_voice: {profile.id}")

        body = {
            "model": MODEL,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": float(p.get("speed", 1.0)),
                "vol": float(p.get("volume", 1.0)),
                "pitch": int(p.get("pitch", 0)),
            },
        }
        try:
            resp = httpx.post(API_URL, headers=self._headers(), json=body, timeout=120)
        except httpx.HTTPError as e:
            raise VoicecastError(f"MiniMax 网络错误: {e}") from e
        d = resp.json()
        if resp.status_code != 200 or d.get("base_resp", {}).get("status_code", 0) != 0:
            raise VoicecastError(f"MiniMax 失败: {d.get('base_resp', d)}")

        audio_hex = d.get("data", {}).get("audio", "")
        if not audio_hex:
            raise VoicecastError(f"MiniMax 响应无音频: {d}")
        out_path.write_bytes(bytes.fromhex(audio_hex))

        v = verify_audio(out_path)
        if not v["ok"]:
            raise VoicecastError(f"MiniMax 输出校验失败: {profile.id} {v['reason']}")
        return out_path

    def clone_voice(self, ref_wav: Path, voice_id: str) -> str:
        """上传参考音频(≥10s) → 克隆 → 立即验证（2054 坑）。返回 voice_id。"""
        if not self.available():
            raise VoicecastError("未配置 MINIMAX_API_KEY")
        with open(ref_wav, "rb") as f:
            resp = httpx.post(
                UPLOAD_URL,
                headers={"Authorization": f"Bearer {os.environ['MINIMAX_API_KEY']}"},
                files={"file": (ref_wav.name, f, "audio/wav")},
                data={"purpose": "voice_clone"},  # 必须放 body，放 header 报 2013
                timeout=180,
            )
        d = resp.json()
        file_id = (d.get("file") or {}).get("file_id")
        if not file_id:
            raise VoicecastError(f"上传失败: {d}")

        r2 = httpx.post(
            CLONE_URL,
            headers=self._headers(),
            json={"file_id": file_id, "voice_id": voice_id, "model": MODEL},
            timeout=120,
        )
        d2 = r2.json()
        if d2.get("base_resp", {}).get("status_code", 0) != 0:
            raise VoicecastError(f"克隆失败: {d2.get('base_resp', d2)}")

        # 关键：克隆返回 OK 不代表落库——立即用该 voice_id 验证（2054）
        verify_path = OUTPUTS_DIR / ".voice_clone_verify.wav"
        last_err: VoicecastError | None = None
        for _ in range(3):
            try:
                self.synthesize(
                    "你好，这是音色验证。",
                    VoiceProfile(id="__verify__", params={"base_voice": voice_id}),
                    verify_path,
                )
                verify_path.unlink(missing_ok=True)
                return voice_id
            except VoicecastError as e:
                last_err = e
                time.sleep(3)
        verify_path.unlink(missing_ok=True)
        raise VoicecastError(f"克隆后验证失败(可能 2054)：{last_err}")

    def explain(self) -> str:
        return f"{self.display_name}（需 MINIMAX_API_KEY）"
