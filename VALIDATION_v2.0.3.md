# MEMÓRIA v2.0.3 — Scientific Council API Budget Optimisation Validation

## Objective

Reduce Mistral API consumption while preserving the Scientific Council grounding, completeness and safety contract from v2.0.2.

## Implemented controls

- Role-specific output ceilings instead of a global 1,200-token ceiling.
- Compact role-specific evidence contexts.
- Compact Chair evidence context.
- Sequential agent execution.
- One logical retry maximum, with a small retry token bonus only when needed.
- Actual request/token accounting from Mistral usage metadata.
- Process-local cache keyed by evidence + agents + model.
- Configurable per-session API-call guard.
- Configurable cooldown between fresh Council runs.

## Default completion ceilings

| Reviewer | Max output tokens |
|---|---:|
| Seismologist | 750 |
| Statistician | 700 |
| Data Quality Auditor | 650 |
| Model Reviewer | 750 |
| Skeptic | 750 |
| Chair | 900 |

A full five-reviewer Council therefore has a normal maximum output ceiling of 4,500 tokens, down from 7,200 tokens in v2.0.2. Actual output is normally lower because these values are ceilings.

## Validation performed

- `python -m compileall -q src app tests` — passed.
- `python -m pytest -q tests/test_v2_scientific_council.py tests/test_assistant_v060.py` — passed.
- `python -m pytest -q tests --ignore=tests/test_similarity.py` — passed.
- `python -m pytest -q tests/test_similarity.py` — passed (7 tests).
- Runtime Streamlit launch was not executed in the build environment because Streamlit is not installed there; `app/streamlit_app.py` compiles successfully.
- Ruff was not available in the build environment.

## Scientific behaviour

No anomaly, b-value, migration, regime, Replay or Model Arena computation was changed. This release changes only how the Scientific Council packages evidence, budgets model output, accounts for usage and reuses identical reviews.
