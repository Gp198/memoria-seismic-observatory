# MEMÓRIA — Portuguese Seismic Memory Observatory

**MEMÓRIA** is an experimental, explainable seismic-intelligence platform for Portugal.

Its core question is:

> Has the current seismic state of a Portuguese tectonic region occurred before, and what followed historically in the most similar states?

MEMÓRIA is **not** an earthquake prediction or public-alert system. It compares present seismic patterns with prior catalogue windows, measures anomalies, runs leakage-safe historical replays, and exposes data quality and uncertainty.

## What is included

- IPMA recent-event ingestion with immutable daily snapshots.
- ISC FDSN event-catalogue ingestion.
- AHEAD/EPICA historical-event ingestion through the official OGC WFS service.
- Generic import path for historical IPMA CSV exports.
- Bronze, Silver and Gold data layers.
- Event harmonisation, source-quality scoring and duplicate grouping.
- Pilot tectonic-domain classification:
  - Southwest Iberian Margin.
  - Lower Tagus Valley.
- Magnitude-of-completeness estimation.
- Rolling seismic-state fingerprints.
- Explainable nearest-state similarity.
- Replay Portugal backtesting with future-data leakage controls.
- Baseline probability comparison and Brier Score.
- Professional Streamlit dashboard.
- Context-aware Mistral explanatory assistant.
- Automated Markdown report generation.
- Unit tests and a scheduled GitHub Actions IPMA snapshot workflow.

## Scientific boundary

The project reports:

- relative activity;
- historical percentile;
- similarity to prior states;
- experimental probabilities;
- data quality and uncertainty.

It must not report:

- a deterministic date, location or magnitude for a future earthquake;
- “imminent earthquake” alerts;
- operational civil-protection instructions;
- scientifically validated public warnings.

The pilot tectonic polygons are **analytical approximations**, not authoritative seismogenic-source models.

## Quick start

### 1. Create a virtual environment

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. Install

```bash
python -m pip install --upgrade pip
pip install -e .
```

### 3. Create a local demonstration dataset

```bash
python -m src.pipeline bootstrap-demo
```

The bundled demonstration data are synthetic and are clearly labelled `DEMO`. They exist only so the complete application can be tested without waiting for historical downloads.

### 4. Run the dashboard

```bash
streamlit run app/streamlit_app.py
```

Windows shortcut:

```cmd
run_local.cmd
```

Ou, em PowerShell:

```powershell
.\run_local.ps1
```

macOS/Linux shortcut:

```bash
chmod +x run_local.sh
./run_local.sh
```

## Use live data

Fetch recent IPMA events and build the Silver and Gold layers:

```bash
python -m src.pipeline run-all --ipma-areas 7 3
```

Fetch an ISC period:

```bash
python -m src.pipeline ingest-isc \
  --start 2000-01-01 \
  --end 2026-12-31 \
  --min-lat 32 --max-lat 44 \
  --min-lon -20 --max-lon -5
```

Fetch AHEAD/EPICA events for the pilot Portugal region:

```bash
python -m src.pipeline ingest-ahead
```

Then rebuild the audited Silver catalogue and both Gold modes:

```bash
python -m src.pipeline build-silver
python -m src.pipeline build-gold --catalogue-mode complete
python -m src.pipeline build-gold --catalogue-mode declustered
python -m src.pipeline merge-gold
python -m src.pipeline report
```

On Windows, `build_gold_all.cmd` runs the three Gold commands in separate
processes to keep memory bounded.

## Data directories

```text
data/
├── bronze/       # Immutable source snapshots.
├── silver/       # Harmonised event catalogue.
├── gold/         # Fingerprints and analytical outputs.
└── sample/       # Synthetic local demonstration data.
```

Bronze files should not be edited after ingestion. A changed source response is saved as a new timestamped file.

## Main commands

```bash
python -m src.pipeline bootstrap-demo
python -m src.pipeline ingest-ipma --ipma-areas 7 3
python -m src.pipeline ingest-isc --start 2000-01-01 --end 2026-12-31
python -m src.pipeline ingest-ahead
python -m src.pipeline build-silver
python -m src.pipeline build-gold --catalogue-mode complete
python -m src.pipeline build-gold --catalogue-mode declustered
python -m src.pipeline merge-gold
python -m src.pipeline validate-grid --catalogue-mode complete
python -m src.pipeline report
python -m src.pipeline run-all
pytest
ruff check .
```

## Dashboard pages

1. **Estado atual** — event map, activity KPIs, time series and regional state.
2. **Memória semelhante** — nearest historical fingerprint windows with feature-level explanations.
3. **Replay Portugal** — historical simulation that only uses data known at the selected replay date.
4. **Qualidade e metodologia** — source coverage, completeness, exclusions and limitations.



## Assistente MEMÓRIA com Mistral

A v0.6.1 inclui um chatbot contextual na barra lateral. O assistente explica a
página atual, percentis, incerteza, declustering, políticas de magnitude,
analogias e Replay Portugal.

Configuração rápida no Windows CMD:

```cmd
set MISTRAL_API_KEY=a_tua_chave
set MEMORIA_MISTRAL_MODEL=mistral-small-latest
python -m streamlit run app\streamlit_app.py
```

Também podes usar `.streamlit/secrets.toml` a partir do exemplo incluído. Sem
uma chave configurada, a aplicação continua totalmente funcional e o painel do
assistente apresenta apenas as instruções de configuração.

O assistente recebe apenas métricas agregadas da página e não recebe linhas
brutas do catálogo. Não é um sistema de previsão nem uma fonte oficial.
Consulta `docs/assistant_v0.6.1.md` para arquitetura, privacidade e limites.

## Automated daily IPMA snapshots

A GitHub Actions workflow is included in:

```text
.github/workflows/daily-ipma.yml
```

It runs every day, stores a timestamped Bronze snapshot, rebuilds the analytical layers and commits changed data. Repository Actions need `Read and write permissions` enabled for the workflow token.

## Recommended scientific review before publication

- Confirm and replace pilot domain polygons with peer-reviewed or official geospatial definitions.
- Validate magnitude harmonisation decisions.
- Review catalogue completeness per domain and epoch.
- Validate duplicate thresholds.
- Audit every replay for temporal leakage.
- Agree communication language with a qualified seismologist.
- Do not deploy public notifications without IPMA/ANEPC governance.

## Official data services used

- IPMA open-data seismic JSON: `https://api.ipma.pt/open-data/observation/seismic/`
- ISC FDSN Event Web Service: `https://www.isc.ac.uk/fdsnws/event/1/`
- AHEAD/EPICA OGC WFS: `https://www.emidius.eu/services/europe/wfs`

Consult each provider’s citation, licensing and usage guidance before public redistribution.

## Project status

This repository implements the complete **12-week MVP architecture** as a working local prototype. It does not claim that all historical Portuguese catalogues are already complete or scientifically reconciled. Historical IPMA files and specialist-reviewed tectonic polygons still require acquisition and expert validation.


## Windows troubleshooting

See `docs/windows_installation.md` for installation errors, virtual-environment activation and PATH guidance.


## Corporate HTTPS certificates

The application uses the operating-system trust store through `truststore`.
This supports Windows environments where a corporate proxy, VPN or antivirus
adds an internal certificate authority.

After updating the project:

```cmd
.venv\Scripts\activate
python -m pip install --upgrade -e .
python -m src.pipeline tls-diagnostics
```

A custom PEM chain can be configured with:

```cmd
set MEMORIA_CA_BUNDLE=C:\certificates\enterprise-root-chain.pem
```

See `docs/windows_certificates.md`.


### Scientific validation layer

Version 0.3.0 added non-overlapping temporal families, effective sample size,
percentile uncertainty intervals, epoch-segmented histories and time-safe
walk-forward calibration.

Version 0.4.0 adds uncertainty-aware state classification, moving-block
bootstrap intervals, complete-versus-declustered sensitivity analysis,
magnitude provenance, adaptive temporal regimes and validation matrices by
magnitude and horizon. See `docs/scientific_integrity_v0.5.0.md`.


## v0.5.0 — Scientific integrity and rare-event validation

- full declustering reconciliation, including ineligible-event reasons;
- operational versus reviewed-only magnitude policies;
- four Gold combinations (catalogue mode × magnitude policy);
- calibration confidence intervals and minimum-sample status;
- rare-event decision thresholds and Precision–Recall analysis;
- automatic map framing and density-grid resolution disclosure.


## v0.6.1 — Assistente explicativo Mistral

- chatbot contextual disponível na barra lateral sem alterar os cálculos;
- contexto limitado a métricas agregadas e opções da interface;
- explicações específicas para Visão geral, Memória semelhante, Replay e Qualidade;
- limites científicos incorporados no system prompt;
- chave por variável de ambiente, Streamlit secrets ou sessão temporária;
- timeout, retries e tratamento de 401, 402, 429, 5xx e falhas TLS;
- nenhuma reconstrução Silver ou Gold necessária.

## Autoria e relação institucional

O MEMÓRIA foi criado e é desenvolvido por **Gonçalo Pedro**. É um projeto experimental independente. Não é um projeto, produto, iniciativa ou serviço oficial do IPMA. O IPMA é uma fonte pública de dados integrada e a referência oficial para informação sísmica e segurança pública em Portugal.
