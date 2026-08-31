#!/usr/bin/env bash
# VoiceCast 本地引擎环境搭建：torch(cu128) + F5-TTS + 模型下载
set -e
cd /d/VoiceCast
PY=.venv/Scripts/python.exe

echo "=== [1/4] torch cu128 (RTX 5060 Blackwell) ==="
uv pip install --python .venv torch torchaudio --index-url https://download.pytorch.org/whl/cu128 || {
  echo "[warn] pytorch.org 失败，切阿里镜像重试..."
  uv pip install --python .venv torch torchaudio --index-url https://mirrors.aliyun.com/pytorch-wheels/cu128/
}
"$PY" -c "import torch;print('torch',torch.__version__,'| cuda:',torch.cuda.is_available(),'|',torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO-GPU')"

echo "=== [2/4] f5-tts + huggingface_hub ==="
uv pip install --python .venv -i https://pypi.tuna.tsinghua.edu.cn/simple f5-tts huggingface_hub
"$PY" -c "import f5_tts;print('f5-tts import ok')"

echo "=== [3/4] F5-TTS 模型下载 (hf-mirror) ==="
export HF_ENDPOINT=https://hf-mirror.com
"$PY" - <<'EOF'
import os
from huggingface_hub import snapshot_download
os.makedirs("models", exist_ok=True)
p = snapshot_download(repo_id="SWivid/F5-TTS", local_dir="models/F5-TTS")
print("model dir:", p)
EOF

echo "=== [4/4] 模型文件核对 ==="
"$PY" - <<'EOF'
import glob
for f in sorted(glob.glob("models/F5-TTS/**/*", recursive=True)):
    import os
    if os.path.isfile(f):
        print(f, f"{os.path.getsize(f)/1024/1024:.1f}MB")
EOF

echo "LOCAL_ENGINE_SETUP_DONE"
