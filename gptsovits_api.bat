@echo off
REM VoiceCast GPT-SoVITS API launcher (RTX 50 nvidia50 build)
cd /d D:\VoiceCast\.cache_tmp\gpt-sovits\extracted\GPT-SoVITS-v2pro-20250604-nvidia50
start "GPT-SoVITS-API" runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880
echo GPT-SoVITS API starting at http://127.0.0.1:9880 (model load ~1-2 min)
