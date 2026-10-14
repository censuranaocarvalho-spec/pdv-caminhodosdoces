@echo off
cd /d "%~dp0\.."
where git >nul 2>&1
if errorlevel 1 (
  echo Falta o Git. A pagina de instalar vai abrir.
  echo Instale e depois de dois cliques neste arquivo de novo.
  start https://git-scm.com/download/win
  pause
  exit /b 1
)
if not exist ".git" git init -b main
git remote remove origin >nul 2>&1
git remote add origin https://github.com/censuranaocarvalho-spec/pdv-caminhodosdoces.git
echo Entre com a conta do GitHub se o navegador abrir.
git fetch origin
if errorlevel 1 (
  echo Nao entrou. Entre com a conta censuranaocarvalho-spec e clique de novo.
  pause
  exit /b 1
)
git checkout -f -B main origin/main
git branch --set-upstream-to=origin/main main
echo.
echo Pronto. O Git da loja esta ligado. Abra com iniciar.bat
pause
