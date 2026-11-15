@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo LitDex 15 - Instalar dependencias e executar testes
echo ============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo ERRO: o Python Launcher ^(comando py^) nao foi encontrado.
  echo Instale Python 3.11 ou superior em https://www.python.org/downloads/windows/
  echo Marque a opcao para instalar o Python Launcher e tente novamente.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Criando ambiente virtual isolado .venv...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo ERRO: nao foi possivel criar o ambiente virtual.
    pause
    exit /b 1
  )
) else (
  echo [1/3] Ambiente virtual .venv ja existe.
)

echo.
echo [2/3] Instalando dependencias de execucao...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERRO: a instalacao falhou. Verifique a conexao com a internet e a versao do Python.
  pause
  exit /b 1
)

echo.
echo [3/3] Executando a suite de testes (unittest, sem dependencias extras)...
".venv\Scripts\python.exe" -m unittest discover -s tests -t . -v
set TEST_EXIT=%ERRORLEVEL%
echo.
if "%TEST_EXIT%"=="0" (
  echo SUCESSO: todos os testes passaram.
) else (
  echo ATENCAO: a suite terminou com codigo %TEST_EXIT%. Leia o resumo acima.
)
echo.
pause
exit /b %TEST_EXIT%
