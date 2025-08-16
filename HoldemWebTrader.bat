@echo off
cd /d "%~dp0backend"
start /B python main.py
timeout /t 3 /nobreak > nul
start http://localhost:8000
exit