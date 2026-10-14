@echo off
cd /d "%~dp0\.."
if not exist ".git" (
  echo A pasta ainda nao esta ligada. De dois cliques em ligar.bat
  pause
  exit /b 1
)
set "GIT="
where git >nul 2>&1 && set "GIT=git"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if not defined GIT (
  echo Falta o Git.
  pause
  exit /b 1
)
echo Baixando a atualizacao da loja...
"%GIT%" pull --ff-only origin main
if errorlevel 1 (
  echo Nao baixou. Se o navegador abrir, entre com a conta censuranaocarvalho-spec e clique de novo.
  pause
  exit /b 1
)
echo.
echo Pronto. No navegador do PDV, aperte F5.
pause
