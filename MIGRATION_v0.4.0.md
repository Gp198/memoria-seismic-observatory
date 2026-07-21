# MEMÓRIA v0.4.0 — aplicação do patch

## Reconstrução obrigatória

A versão acrescenta proveniência de magnitude, auditoria de homogeneização,
anotação de sequências e dois modos de catálogo. Por isso, Silver e Gold
precisam de ser reconstruídos.

```cmd
cd C:\memoria-seismic-observatory
.venv\Scripts\activate
python -m pip install --upgrade -e .
python -m src.pipeline clean-derived
python -m src.pipeline build-silver
build_gold_all.cmd
python -m src.pipeline report
python -m src.pipeline data-status
python -m streamlit cache clear
python -m streamlit run app\streamlit_app.py
```

A camada Bronze e os snapshots das fontes não são eliminados.

## Validação científica opcional

```cmd
python -m src.pipeline validate-grid --catalogue-mode complete
python -m src.pipeline validate-grid --catalogue-mode declustered
```
