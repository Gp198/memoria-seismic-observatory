$ErrorActionPreference = "Stop"

Write-Host "MEMÓRIA - preparação do ambiente local" -ForegroundColor Cyan

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "O Python Launcher 'py' não foi encontrado. Instale Python 3.11 ou 3.12 de python.org."
}

if (-not (Test-Path ".venv")) {
    Write-Host "A criar ambiente virtual .venv..." -ForegroundColor Yellow
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Python 3.12 não disponível. A tentar Python 3.11..." -ForegroundColor Yellow
        py -3.11 -m venv .venv
    }
}

$python = Join-Path $PWD ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Não foi possível criar o ambiente virtual."
}

Write-Host "A atualizar pip, setuptools e wheel..." -ForegroundColor Yellow
& $python -m pip install --upgrade pip setuptools wheel

Write-Host "A instalar a aplicação e dependências..." -ForegroundColor Yellow
& $python -m pip install --upgrade -e .

if (-not (Test-Path "data\silver\events.csv") -and -not (Test-Path "data\silver\events.parquet")) {
    Write-Host "A criar dados de demonstração..." -ForegroundColor Yellow
    & $python -m src.pipeline bootstrap-demo
}

Write-Host "A iniciar o dashboard em http://localhost:8501" -ForegroundColor Green
& $python -m streamlit run app\streamlit_app.py
