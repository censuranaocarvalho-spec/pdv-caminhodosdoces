@echo off
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
  echo Primeiro de dois cliques em instalar.bat
  pause
  exit /b 1
)
echo O PDV abre em http://127.0.0.1:8090
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8090"
.venv\Scripts\python.exe main.py
pause
