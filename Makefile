.PHONY: install demo run test lint live report

install:
	python -m pip install --upgrade pip
	pip install -e ".[dev]"

demo:
	python -m src.pipeline bootstrap-demo

run:
	streamlit run app/streamlit_app.py

test:
	pytest

lint:
	ruff check .

live:
	python -m src.pipeline run-all --ipma-areas 7 3

report:
	python -m src.pipeline report
