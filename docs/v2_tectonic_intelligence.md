# MEMÓRIA v2.0 — Explainable Seismic & Tectonic Intelligence Platform

## Scope

v2.0 expands MEMÓRIA from historical seismic-state comparison into an experimental research platform for:

- statistical seismic anomaly detection;
- Gutenberg–Richter b-value monitoring;
- epicentral and depth migration analysis;
- recurring seismic regime discovery and transition analysis;
- a reproducible Model Arena with Poisson, empirical, historical-family and ETAS-lite baselines;
- optional fault, GNSS and InSAR context;
- evidence graphs that trace conclusions to calculated signals;
- an agentic Scientific Council (Seismologist, Statistician, Data Quality Auditor, Model Reviewer, Skeptic and Chair).

## Scientific boundary

The anomaly engine detects deviations in observed seismic behaviour. It does **not** infer that a large earthquake is imminent. A statistical anomaly is only promoted to a tectonic interpretation when independent geophysical evidence is available and specialist review supports the interpretation.

## Anomaly consensus

The engine combines five independent signals:

1. robust univariate deviations;
2. robust multivariate Mahalanobis distance;
3. Isolation Forest;
4. CUSUM/EWMA change detection;
5. temporal persistence.

A consensus score is transparent and decomposable. Every component remains visible.

## Gutenberg–Richter

The b-value uses the Aki maximum-likelihood estimator above a supplied completeness magnitude Mc. It is disabled when the sample is insufficient. Results are experimental until magnitude homogenisation is scientifically reviewed.

## ETAS-lite

ETAS-lite is a transparent temporal self-exciting **experimental baseline**, not a claim of a fully calibrated ETAS implementation. It separates background expectation from triggered expectation using a conservative Omori-like kernel and exposes its assumptions.

## Multimodal evidence

No GNSS, InSAR or fault geometry is fabricated. Optional integrations activate only when reviewed local data are provided:

- `data/external/gnss.csv`
- `data/external/insar.csv`
- `config/faults.geojson`

## Scientific Council

LLM agents never modify data or model outputs. They receive an aggregated evidence package and independently critique it. The Skeptic agent is explicitly instructed to seek alternative explanations and failure modes. The Chair preserves disagreements rather than forcing consensus.


## v2.0.2 Scientific Council grounding contract

The Council is now evidence-closed by default. Every run receives a `grounding_manifest` containing the effective evidence date (last event timestamp for the selected domain), loaded catalogue sources, and explicit availability flags for fault, GNSS, InSAR and Model Arena context. Agents may not introduce named external entities that are absent from this package.

Each reviewer must return all four required sections. Responses reported as token-limited, missing mandatory sections, or failing the grounding audit are automatically retried once with a corrective instruction. A second failure is not silently displayed: MEMÓRIA returns a safe research-only fallback and marks grounding as rejected. The Chair follows the same completeness/grounding contract and cannot use date placeholders.

Council outputs remain interpretive audit artefacts. They never modify catalogue data, anomaly calculations, b-values, migration estimates, regimes, Model Arena scores or any other scientific computation.

## v2.0.3 Scientific Council API-budget optimisation

v2.0.3 reduces Mistral Free-tier pressure without weakening the grounding safeguards introduced in v2.0.2.

Key changes:

- role-specific completion ceilings: Seismologist 750, Statistician 700, Data Quality Auditor 650, Model Reviewer 750, Skeptic 750 and Chair 900 tokens;
- a retry receives only a small +150-token allowance and remains limited to one logical retry;
- each reviewer receives a compact JSON evidence package containing only the fields needed for that specialty;
- the Chair receives a deterministic compact evidence summary plus grounded reviewer outputs rather than the full repeated evidence package;
- reviewer calls remain sequential to avoid request bursts on low-rate API tiers;
- actual prompt/completion/total token usage and request counts are captured when Mistral returns usage metadata;
- a process-local cache is keyed by evidence hash + selected agents + model, so identical Scientific Council requests can be reused with zero new API calls;
- a configurable session API-call guard and cooldown reduce accidental quota exhaustion in public Streamlit deployments.

Runtime controls:

```text
MEMORIA_COUNCIL_MODEL=mistral-small-latest
MEMORIA_COUNCIL_MAX_API_CALLS_SESSION=16
MEMORIA_COUNCIL_COOLDOWN_SECONDS=30
```

The cache stores Council results only. It never stores the Mistral API key.


## v2.0.4 Scientific robustness and global benchmarking

v2.0.4 closes four research-preview gaps:

1. **Semantic grounding guard** — GNSS/InSAR may be mentioned as missing data or future work without triggering a false violation; affirmative claims still fail grounding when the relevant context is absent. If no reviewer passes grounding, the Chair LLM is skipped and a deterministic research-only fallback is shown, saving API calls.
2. **Audited b-value population** — operational b-values are estimated only on the dominant same-source + same-original-scale cohort in the current observation epoch. Validated mode uses only reviewed identity/conversion records. Sampling sigma is explicitly separated from systematic catalogue uncertainty and values below 0.005 are no longer rendered as `±0.00`.
3. **Regime semantics** — the UI states explicitly that a statistical regime is a recurrent fingerprint class, an anomaly is a deviation from reference, and a tectonic interpretation requires independent physical evidence.
4. **Global Model Arena** — users can run a magnitude × horizon grid, inspect scenario metrics, BSS heatmaps and a global leaderboard based on scenario-level Brier ranks, wins, skill vs Poisson and average precision. The leaderboard is an experimental summary, not a pooled earthquake probability.
