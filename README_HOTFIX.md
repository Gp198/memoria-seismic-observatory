# MEMÓRIA v2.0.1 — Model Arena Timedelta Hotfix

Corrige o erro do Model Arena:

`Result is too large for pandas.Timedelta...`

## Causa
O catálogo do MEMÓRIA pode exceder ~292 anos. `pandas.Timestamp`/`Timedelta` em resolução de nanossegundos pode fazer overflow ao calcular exposições e intervalos sobre todo o arquivo histórico.

## Correção
- diferenças temporais longas no ETAS-lite passam a usar `datetime.datetime` nativo;
- intervalos consecutivos do catálogo deixam de usar `Series.diff()` quando podem atravessar séculos;
- teste de regressão com eventos entre 1719 e 2026;
- versão atualizada para 2.0.1.

## Instalação Windows CMD
Com o Streamlit parado, copie o conteúdo deste patch sobre a raiz do projeto e aceite substituir os ficheiros.

Depois execute:

```cmd
cd C:\memoria-seismic-observatory
.venv\Scripts\activate
python -m pip install --upgrade -e .
python -m pytest -q tests\test_v2_regimes_etas.py
python -m streamlit cache clear
python -m streamlit run app\streamlit_app.py
```

Não é necessário reconstruir Bronze, Silver ou Gold.
