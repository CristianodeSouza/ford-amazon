@echo off
chcp 65001 >nul
echo.
echo  ================================================
echo   Ford Amazon - Conciliacao Dashboard
echo   Projeto: C:\Users\User\ford\
echo  ================================================
echo.

set FORD_ROOT=%~dp0

if not exist "%FORD_ROOT%credentials.json" (
  echo  AVISO: credentials.json nao encontrado!
  echo  Execute primeiro: python setup_google.py
  echo.
  pause
  exit /b
)

if not exist "%FORD_ROOT%token.json" (
  echo  Token Google nao encontrado. Executando setup...
  cd /d "%FORD_ROOT%"
  python setup_google.py
  echo.
)

echo [1/2] Instalando dependencias...
cd /d "%FORD_ROOT%dashboard\backend"
pip install -r requirements.txt -q

echo [2/2] Iniciando servidor na porta 8001...
start "Ford Dashboard Server" python main.py
timeout /t 3 /nobreak >nul

echo  Abrindo: http://localhost:8001
start "" "http://localhost:8001"
echo.
echo  Para parar: feche a janela "Ford Dashboard Server"
echo.
pause
