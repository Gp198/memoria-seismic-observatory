@echo off
setlocal
cd /d C:\memoria-seismic-observatory
call .venv\Scripts\activate
python -m pip install --upgrade -e .
python -m streamlit cache clear
echo.
echo Patch v0.6.2 aplicado. Inicie com:
echo python -m streamlit run app\streamlit_app.py
endlocal
