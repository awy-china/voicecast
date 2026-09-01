"""GPT-SoVITS 引擎：本地生产级克隆（HTTP 对接 api_v2.py 服务）。

- 定位：比 F5-TTS 更强的中文零样本克隆 + 情感/语速控制，MIT 全链可商用。
- 形态：独立服务（整合包自带环境跑 api_v2.py，默认端口 9880），
  本项目只做 HTTP 客户端——不引入 GPT-SoVITS 依赖，零冲突。
- 配方参数：ref_audio_path（参考音频绝对路径，必填）、prompt_text（参考文本）、
  text_lang（默认 zh）、speed（倍率）。
- 服务未启动时 available()=False，路由自动跳过（不报错）。
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

from ..core.models import VoiceProfile, VoicecastError
from .base import Engine
from .util import verify_audio

DEFAULT_URL = os.environ.get("GPT_SOVITS_URL", "http://127.0.0.1:9880")


class GPTSovitsEngine(Engine):
    name = "gpt_sovits"
    display_name = "GPT-SoVITS（本地，生产级克隆）"

    def __init__(self, base_url: str = DEFAULT_URL, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/", timeout=3)
            return r.status_code < 500
        except Exception:  # noqa: BLE001
            return False

    def explain(self) -> str:
        return f"{self.display_name}（{self.base_url}，0 元）"

    def synthesize(
        self, text: str, profile: VoiceProfile, out_path: Path, emotion: str = ""
    ) -> Path:
        p = profile.params
        ref = p.get("ref_audio_path") or p.get("refer_wav_path") or p.get("ref_file")
        if not ref:
            raise VoicecastError(f"GPT-SoVITS 配方缺少参考音频（{profile.id}）")
        ref = str(Path(ref).resolve() if not str(ref).startswith(("http", "\\")) else ref)

        speed = float(p.get("speed", 1.0))
        payload = {
            "text": text,
            "text_lang": str(p.get("text_lang", "zh")),
            "ref_audio_path": ref,
            "prompt_text": str(p.get("prompt_text", "")),
            "prompt_lang": str(p.get("prompt_lang", "zh")),
            "speed_factor": speed,
            "top_k": int(p.get("top_k", 5)),
            "top_p": float(p.get("top_p", 0.95)),
            "temperature": float(p.get("temperature", 0.5)),
        }

        # api_v2 不同版本参数名有差异：旧版 refer_wav_path / 新版 ref_audio_path
        last_err: Exception | None = None
        for _attempt in range(2):
            try:
                r = httpx.post(
                    f"{self.base_url}/tts", json=payload,  # FastAPI Pydantic 模型 → JSON body
                    timeout=self.timeout, follow_redirects=True,
                )
                r.raise_for_status()
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                if "ref_audio_path" not in payload:
                    raise
                payload.pop("ref_audio_path", None)
                payload["refer_wav_path"] = ref
        else:
            raise VoicecastError(f"GPT-SoVITS 服务调用失败: {last_err}")

        ctype = r.headers.get("content-type", "")
        if "json" in ctype:
            # 新版可能返回 {code,msg,data:[urls]} 或 {code,msg,audio}
            try:
                data = r.json()
            except Exception:  # noqa: BLE001
                raise VoicecastError(f"GPT-SoVITS 返回异常: {r.text[:200]}")
            if data.get("code") not in (0, None, "0"):
                raise VoicecastError(f"GPT-SoVITS 错误: {data.get('msg', data)}")
            url = data.get("url") or (data.get("data") or [None])[0] if isinstance(
                data.get("data"), list) else data.get("data")
            if url and isinstance(url, str):
                r = httpx.get(url if url.startswith("http") else f"{self.base_url}{url}",
                              timeout=self.timeout)
                r.raise_for_status()
            else:
                raise VoicecastError(f"GPT-SoVITS 未返回音频: {str(data)[:200]}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)
        v = verify_audio(out_path)
        if not v["ok"]:
            raise VoicecastError(f"GPT-SoVITS 输出校验失败: {profile.id} {v['reason']}")
        return out_path
