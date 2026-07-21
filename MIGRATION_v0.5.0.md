# Migration to MEMÓRIA v0.5.0

Bronze data is preserved. Silver and Gold must be rebuilt because the event
schema and fingerprint dimensions changed.

```cmd
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

The validated magnitude Gold may be sparse until reviewed conversion rules are
added to `config\magnitude_conversion_policy.json`.
