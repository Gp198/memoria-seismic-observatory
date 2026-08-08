# MEMÓRIA v2.0.4 — Scientific Robustness & Global Benchmarking

## Scope

This release hardens the Scientific Council grounding semantics, b-value methodology, regime wording and Model Arena benchmarking.

## Scientific Council

- Absence/future-work references to GNSS or InSAR are allowed when those datasets are not loaded.
- Affirmative claims such as “GNSS confirms deformation” remain blocked without loaded evidence.
- Named external catalogues/faults remain blocked unless explicitly present in the evidence package.
- If zero reviewers pass grounding, the Chair LLM is not called; a deterministic research-only fallback is returned.

## Gutenberg–Richter b

- Operational mode no longer estimates b from a mixture of magnitude scales.
- The selected operational population is restricted to the dominant source + original magnitude type in the current observation epoch.
- Validated mode only admits reviewed/approved magnitude identity/conversion records.
- The displayed sigma is labelled as sampling/statistical uncertainty only. Very small sigma is shown as `<0.01` rather than `0.00`.
- Systematic catalogue uncertainty remains explicit.

## Seismic regimes

The UI distinguishes:

- **Statistical regime**: recurrent fingerprint class.
- **Statistical anomaly**: deviation from a comparable reference population.
- **Tectonic interpretation**: physical hypothesis requiring independent geophysical evidence and specialist review.

## Model Arena

- Single-scenario benchmarking remains available.
- New magnitude × horizon grid supports up to 20 scenarios per run.
- New global leaderboard reports scenario count, mean/median BSS vs Poisson, average precision, Brier wins, mean Brier rank and positive-skill rate.
- Global ranking is scenario-normalised; it is not a pooled probability model.

## Safety position

MEMÓRIA remains research-only. No output constitutes earthquake prediction, public warning, official hazard assessment or evidence of an imminent event.
