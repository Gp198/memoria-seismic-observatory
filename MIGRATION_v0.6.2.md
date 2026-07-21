# Migration to MEMÓRIA v0.6.2

1. Stop Streamlit with `Ctrl+C`.
2. Copy the patch files over the project and accept replacement.
3. Activate the virtual environment.
4. Run `python -m pip install --upgrade -e .`.
5. Run `python -m streamlit cache clear`.
6. Start with `python -m streamlit run app\streamlit_app.py`.

No Bronze, Silver or Gold rebuild is required.
