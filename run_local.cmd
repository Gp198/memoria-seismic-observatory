@echo off
setlocal
cd /d "%~dp0"

echo MEMORIA - preparacao do ambiente local

where py >nul 2>nul
if errorlevel 1 (
    echo ERRO: O Python Launcher "py" nao foi encontrado.
    echo Instale Python 3.11 ou 3.12 a partir de python.org.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo A criar ambiente virtual com Python 3.12...
    py -3.12 -m venv .venv
    if errorlevel 1 (
        echo Python 3.12 nao disponivel. A tentar Python 3.11...
        py -3.11 -m venv .venv
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo ERRO: Nao foi possivel criar o ambiente virtual.
    pause
    exit /b 1
)

set PYTHON=.venv\Scripts\python.exe

echo A atualizar pip...
"%PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

echo A instalar a aplicacao...
"%PYTHON%" -m pip install --upgrade -e .
if errorlevel 1 goto :error

if not exist "data\silver\events.csv" (
    echo A criar dados de demonstracao...
    "%PYTHON%" -m src.pipeline bootstrap-demo
    if errorlevel 1 goto :error
)

echo A iniciar o dashboard...
"%PYTHON%" -m streamlit run app\streamlit_app.py
goto :eof

:error
echo.
echo A instalacao falhou. Reveja as mensagens acima.
pause
exit /b 1
