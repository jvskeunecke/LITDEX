@echo off
setlocal
cd /d "%~dp0"
title LitDex 15

echo ============================================================
echo  LitDex 15 - inicializacao
echo ============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo ERRO: o comando "py" nao foi encontrado.
  echo Instale Python 3.11 ou superior e marque "Python Launcher".
  echo https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

if not exist ".venv\\Scripts\\python.exe" (
  echo [1/3] Criando ambiente virtual...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo ERRO ao criar .venv. Verifique a instalacao do Python.
    pause
    exit /b 1
  )
) else (
  echo [1/3] Ambiente virtual encontrado.
)

echo.
echo [2/3] Conferindo e instalando dependencias...
".venv\\Scripts\\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERRO: nao foi possivel instalar as dependencias.
  echo Verifique a internet e tente novamente.
  pause
  exit /b 1
)

echo.
echo [3/3] Iniciando LitDex...
echo A janela do navegador sera aberta quando o servidor estiver pronto.
echo Para encerrar, feche esta janela ou pressione Ctrl+C.
echo.
".venv\\Scripts\\python.exe" -u litdex.py
set APP_EXIT=%ERRORLEVEL%

echo.
if not "%APP_EXIT%"=="0" (
  echo LitDex encerrou com codigo %APP_EXIT%.
  echo Copie a mensagem de erro acima para o diagnostico.
) else (
  echo LitDex foi encerrado.
)
pause
exit /b %APP_EXIT%
