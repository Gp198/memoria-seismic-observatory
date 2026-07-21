# Instalação no Windows

## Método recomendado

Abra a pasta do projeto e execute:

```cmd
run_local.cmd
```

O script cria o ambiente virtual, instala as dependências, prepara os dados de demonstração e abre o Streamlit.

## Instalação manual

Na Linha de Comandos:

```cmd
cd C:\memoria-seismic-observatory
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m src.pipeline bootstrap-demo
python -m streamlit run app\streamlit_app.py
```

Também podes usar Python 3.11:

```cmd
py -3.11 -m venv .venv
```

## Porque ocorreu o erro do Ruff

O comando:

```cmd
pip install -e ".[dev]"
```

instalava também ferramentas opcionais de desenvolvimento. O índice de pacotes utilizado pelo computador não encontrou uma distribuição compatível do `ruff`, pelo que o `pip` cancelou toda a instalação. Como consequência:

- `pandas` não foi instalado;
- `streamlit` não foi instalado;
- os comandos seguintes falharam.

A versão corrigida deixa `ruff` num extra independente:

```cmd
python -m pip install -e ".[lint]"
```

O `ruff` não é necessário para executar a aplicação.

## Streamlit não reconhecido

Use sempre:

```cmd
python -m streamlit run app\streamlit_app.py
```

Isto evita problemas com o PATH do Windows.

## Confirmar o ambiente ativo

Depois de executar:

```cmd
.venv\Scripts\activate
```

a linha de comandos deverá começar por:

```text
(.venv) C:\memoria-seismic-observatory>
```

Mesmo sem ativação manual, os scripts `run_local.cmd` e `run_local.ps1` chamam diretamente o Python do ambiente virtual.
