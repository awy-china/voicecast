@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, 'src'); from voicecast.cli.main import app; app()" %*
