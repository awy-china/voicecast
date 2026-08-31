@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -c "import sys; sys.path.insert(0, 'src'); from voicecast.web.app import build_app; build_app().launch(server_name='127.0.0.1', server_port=7860, inbrowser=True)"
