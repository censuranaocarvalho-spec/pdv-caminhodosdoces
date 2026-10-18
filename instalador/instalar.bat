@echo off
cd /d "%~dp0\.."
where python >nul 2>&1
if errorlevel 1 (
  echo Falta o Python. Baixe em https://www.python.org/downloads/windows/
  echo Na instalacao, marque Add python.exe to PATH.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
echo Pronto. Agora de dois cliques em iniciar.bat
pause
