# Methodology

## 1. Ingestion and provenance

Each source response is stored in the Bronze layer under a timestamped path. Raw snapshots are never overwritten. A SHA-256 digest is stored beside each response.

## 2. Harmonisation

Source-specific records are mapped to the common Silver schema. Source values remain available. The first MVP does not silently convert every magnitude scale into Mw.

## 3. Duplicate detection

Probable duplicate records are grouped when all conditions are met:

- origin-time difference is within the configured threshold;
- epicentral distance is within the configured threshold;
- magnitude difference is within the configured threshold or one magnitude is missing.

The preferred record follows a transparent source and completeness ranking. Non-preferred records remain in the Silver catalogue for auditability.

## 4. Tectonic domains

Events are classified against versioned pilot polygons with Shapely. These polygons are intentionally broad analytical domains. They must be reviewed by a qualified geoscientist before scientific publication.

## 5. Magnitude of completeness

The initial estimator uses maximum curvature on the Gutenberg–Richter frequency-magnitude distribution and returns no estimate when the sample is insufficient. Results are calculated by domain and epoch.

## 6. Fingerprints

Events are grouped into rolling windows. Each fingerprint contains:

- rate;
- maximum and mean magnitude;
- depth statistics;
- spatial dispersion;
- empirical total energy;
- time since a prior M≥3 event;
- completeness;
- quality.

Features are standardised within the training history of the domain.

## 7. Similarity

The system supports:

- Euclidean distance on standardised features;
- Mahalanobis distance with regularised covariance;
- nearest-neighbour analogue retrieval.

Windows that overlap the target or violate the configured temporal exclusion gap are removed.

## 8. Replay Portugal

A replay cutoff simulates knowledge available at a past date. Training fingerprints must end before that cutoff. Future outcomes are measured after the cutoff and are never used to calculate the target state or fit standardisation.

## 9. Baselines

The prototype compares analogue probabilities with:

- historical unconditional event frequency;
- a simple Poisson-rate baseline derived only from prior events.

ETAS is deliberately deferred until catalogue completeness and sequence declustering have been reviewed.

## 10. Evaluation

Recommended metrics:

- Brier Score;
- calibration curve;
- precision and recall at predefined thresholds;
- false alarms per year;
- missed-event count;
- coverage and sharpness;
- performance by domain and epoch.

## 11. Explainability

Each analogue result shows:

- its time period;
- total similarity;
- feature-level differences;
- catalogue quality;
- observed future outcome.

A language summary is generated from those calculations, not from an unconstrained model.


## Scientific comparability revision

See `docs/scientific_adjustments_v0.2.0.md` for epoch-aware percentiles, temporal families and common-exposure baselines.


## Validation and uncertainty revision

Effective sample size, non-overlapping temporal families, segmented epochs and time-safe calibration are documented in `docs/validation_v0.3.0.md`.


## Scientific sensitivity and audit revision

Uncertainty-aware classification, moving-block bootstrap, catalogue
declustering sensitivity, magnitude provenance, adaptive regimes and
multiscenario validation are documented in
`docs/scientific_validation_v0.4.0.md`.

## Scientific integrity and rare-event validation

Version 0.5.0 adds complete declustering reconciliation, operational and
reviewed-only magnitude policies, Wilson intervals for reliability bins,
rare-event decision thresholds and Precision–Recall evaluation. The full
methodological note is available in `docs/scientific_integrity_v0.5.0.md`.
