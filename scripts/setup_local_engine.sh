#!/usr/bin/env bash
# VoiceCast 本地引擎环境：torch(cu128) + F5-TTS + 模型下载
# 关键1：清空 PYTHONPATH（Hermes 会话注入会污染 import/pip 解析）
# 关键2：镜像索引均为扁平目录（非 PEP503），torch 用直链 URL 装，依赖走清华 PyPI
set -e
export PYTHONPATH=
cd /d/VoiceCast
PY=/d/VoiceCast/.venv/Scripts/python.exe
TORCH_URL="https://mirrors.aliyun.com/pytorch-wheels/cu128/torch-2.11.0%2Bcu128-cp311-cp311-win_amd64.whl"
TORCHAUDIO_URL="https://mirrors.aliyun.com/pytorch-wheels/cu128/torchaudio-2.11.0%2Bcu128-cp311-cp311-win_amd64.whl"

echo "=== [1/4] torch cu128 via aliyun direct URL ==="
"$PY" -m pip install "$TORCH_URL" "$TORCHAUDIO_URL" -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300
"$PY" -c "import torch;print('torch',torch.__version__,'| cuda:',torch.cuda.is_available(),'|',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO-GPU')"

echo "=== [2/4] f5-tts + huggingface_hub (tsinghua PyPI) ==="
"$PY" -m pip install f5-tts huggingface_hub -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300
"$PY" -c "import f5_tts;print('f5-tts import ok')"

echo "=== [3/4] F5-TTS model download (hf-mirror) ==="
export HF_ENDPOINT=https://hf-mirror.com
"$PY" - <<'EOF'
import os
from huggingface_hub import snapshot_download
os.makedirs("models", exist_ok=True)
p = snapshot_download(repo_id="SWivid/F5-TTS", local_dir="models/F5-TTS")
print("model dir:", p)
EOF

echo "=== [4/4] model files ==="
"$PY" - <<'EOF'
import glob, os
for f in sorted(glob.glob("models/F5-TTS/**/*", recursive=True)):
    if os.path.isfile(f):
        print(f, f"{os.path.getsize(f)/1024/1024:.1f}MB")
EOF

echo "LOCAL_ENGINE_SETUP_DONE"
