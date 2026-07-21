# 12-week MVP implementation status

## Weeks 1–2 — Foundation

| Planned item | Implementation |
|---|---|
| Create repository | Complete project structure, packaging, local scripts and GitHub workflow. |
| Write vision and boundaries | `README.md`, `docs/scientific_scope.md`, `docs/limitations.md`. |
| Define data schema | `docs/data_dictionary.md`, `src/schema.py`. |
| Implement IPMA ingestion | `src/ingestion/ipma.py`. |
| Store daily snapshots | Timestamped Bronze storage and `.github/workflows/daily-ipma.yml`. |
| Select pilot regions | Southwest Iberian Margin and Lower Tagus Valley in `config/domains.geojson`. |

## Weeks 3–4 — Catalogue

| Planned item | Implementation |
|---|---|
| Import ISC | `src/ingestion/isc.py` using the official FDSN service. |
| Import IPMA catalogues | Generic historical CSV importer in `src/ingestion/ipma.py`. The source catalogues still need to be obtained and mapped. |
| Integrate AHEAD | `src/ingestion/ahead.py` using EPICA WFS. |
| Deduplicate | `src/quality/deduplication.py`. |
| Classify quality | Source and record quality fields in all normalisers. |
| Create Silver catalogue | `src/pipeline.py build-silver`. |

## Weeks 5–6 — Geography and completeness

| Planned item | Implementation |
|---|---|
| Create polygons | Versioned pilot GeoJSON. |
| Classify events | `src/geography/tectonic_domains.py`. |
| Estimate completeness | Maximum-curvature estimator in `src/quality/completeness.py`. |
| Separate comparable periods | Epoch completeness helper and catalogue fields. |
| Quality tests | Pytest suite covering parsers, geography, deduplication and completeness. |

## Weeks 7–8 — Fingerprints

| Planned item | Implementation |
|---|---|
| Rolling windows | 30, 90 and 365-day windows. |
| Calculate features | `src/features/fingerprints.py`. |
| Normalise by region | Training-history standardisation in similarity module. |
| Search analogues | Euclidean and Mahalanobis nearest states. |
| Produce comparisons | Dashboard table and feature-difference chart. |

## Weeks 9–10 — Backtesting

| Planned item | Implementation |
|---|---|
| Replay Portugal | `src/backtesting/replay.py`. |
| Prevent future leakage | Cutoff filtering, exclusion gaps and training-only scaling. |
| Test horizons | 7, 30, 90 and 365 days in the dashboard. |
| Compare baselines | Historical-rate and Poisson baselines. |
| Document false alarms | Walk-forward results and Brier Score. |

## Weeks 11–12 — Initial product

| Planned item | Implementation |
|---|---|
| Build Streamlit | Professional four-page dashboard. |
| Generate report | `src/reporting/explanations.py`. |
| Publish methodology | Documentation under `docs/`. |
| Prepare demonstration | `docs/demo_script.md`. |
| Seek seismologist review | Review checklist prepared; actual external scientific review has not been performed. |

## Remaining work before a scientific release

- Acquire and legally review the full historical IPMA catalogue files.
- Replace pilot polygons with specialist-reviewed boundaries.
- Validate magnitude conversions and catalogue completeness by epoch.
- Add a reviewed ETAS implementation.
- Run sensitivity studies and publish full backtesting results.
- Obtain independent seismologist review.
