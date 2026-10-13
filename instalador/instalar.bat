@echo off
cd /d "%~dp0\.."
where python >nul 2>&1
if errorlevel 1 (
  echo Falta o Python. Baixe em https://www.python.org/downloads/windows/
  echo Na instalacao, marque Add python.exe to PATH.
  pause
  exit /b 1
)
if not exist "core-orders\venv\Scripts\python.exe" (
  python -m venv core-orders\venv
)
core-orders\venv\Scripts\python.exe -m pip install --upgrade pip
core-orders\venv\Scripts\python.exe -m pip install "fastapi>=0.115" "uvicorn>=0.30" "pydantic>=2.10" websocket-client
echo.
echo Pronto. Agora de dois cliques em iniciar.bat
pause
