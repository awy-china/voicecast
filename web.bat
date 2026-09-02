@echo off
cd /d D:\VoiceCast
set PYTHONPATH=src
start "VoiceCast-Web" .venv\Scripts\python.exe -m uvicorn voicecast.web.server:app --host 127.0.0.1 --port 7860
timeout /t 2 >nul
start http://127.0.0.1:7860
