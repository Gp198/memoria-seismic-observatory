MEMÓRIA v2.0.3 — Scientific Council API Budget Optimisation
============================================================

Apply this patch over MEMÓRIA v2.0.2.

What changes
------------
- Per-agent token ceilings instead of max_tokens=1200 for every reviewer.
- Seismologist 750; Statistician 700; Data Quality Auditor 650; Model Reviewer 750; Skeptic 750; Chair 900.
- One retry maximum, with +150 tokens only on the retry.
- Role-specific compact evidence packages to reduce repeated input tokens.
- Compact Chair context.
- Sequential Council calls to reduce rate-limit bursts.
- Actual Mistral request/token accounting in the UI.
- Shared process cache keyed by evidence + agents + model: identical reviews use 0 new API calls.
- Session API-call guard (default 16) and fresh-run cooldown (default 30 seconds).
- Cache bounded to 32 Council results per Streamlit process.

Optional environment settings
-----------------------------
MEMORIA_COUNCIL_MODEL=mistral-small-latest
MEMORIA_COUNCIL_MAX_API_CALLS_SESSION=16
MEMORIA_COUNCIL_COOLDOWN_SECONDS=30

Installation on Windows CMD
---------------------------
1. Stop Streamlit with Ctrl+C.
2. Extract this patch and copy its contents over C:\memoria-seismic-observatory.
3. Activate the virtual environment:
   .venv\Scripts\activate
4. Reinstall editable package metadata:
   python -m pip install --upgrade -e .
5. Test:
   python -m pytest -q tests\test_v2_scientific_council.py tests\test_assistant_v060.py
6. Clear cache and run:
   python -m streamlit cache clear
   python -m streamlit run app\streamlit_app.py

No Bronze, Silver or Gold rebuild is required.
