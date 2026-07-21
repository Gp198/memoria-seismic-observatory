# MEMÓRIA v0.4.0 — Scientific sensitivity and audit release

## Scope

Version 0.4.0 strengthens the scientific audit trail without changing the
central communication rule: MEMÓRIA is an experimental comparison and
backtesting platform, not an earthquake-warning or deterministic prediction
system.

## Uncertainty-aware state classification

The state badge no longer uses the central percentile alone. It evaluates:

- the percentile estimate;
- a conservative interval combining the effective-sample Wilson interval and
  a moving-block bootstrap interval;
- the effective sample size;
- whether the complete interval lies above or below the pilot elevation
  threshold.

The possible conclusions are:

- no robust evidence of elevation;
- inconclusive because the interval crosses the threshold;
- inconclusive because the effective sample is too small;
- elevated activity with statistical support;
- exceptionally elevated activity with statistical support.

The bootstrap samples contiguous blocks of moving windows to preserve local
temporal dependence. It remains a sensitivity analysis and is not a complete
point-process uncertainty model.

## Catalogue sensitivity and pilot declustering

Silver events are annotated with:

- `cluster_id`;
- `cluster_role`;
- `is_background_event`;
- `declustering_method`.

The pilot algorithm selects potential mainshocks and associates later,
lower-or-equal magnitude events inside transparent adaptive space-time
windows. It uses a spatial BallTree for scalable neighbourhood queries.

This method is intentionally labelled
`pilot_adaptive_space_time_v1`. It is not claimed to be an official
Gardner–Knopoff, Reasenberg or ETAS implementation. The application exposes
both the complete and pilot-declustered catalogues so conclusions can be
compared rather than silently replacing one catalogue with another.

## Magnitude provenance and operational homogenisation

The Silver schema now preserves:

- original magnitude value;
- original magnitude type;
- operational comparison value;
- conversion method;
- conversion equation;
- conversion uncertainty;
- review status.

Moment-magnitude variants use an identity mapping. No unreviewed empirical
conversion coefficients are shipped by default. Other scales retain their
numeric value only as a clearly flagged operational fallback, with wider
uncertainty and `review_required` status.

Reviewed affine conversion rules can later be supplied in:

```text
config/magnitude_conversion_policy.json
```

A sismologist should approve those rules before scientific publication.

## Adaptive temporal regimes

The similarity engine offers two family methods:

- fixed temporal width;
- adaptive regime detection.

The adaptive method detects robust changes across event rate, maximum
magnitude, estimated energy and spatial dispersion. It also imposes a maximum
regime duration and a non-overlap buffer. This is a transparent change-point
heuristic, not a physical definition of a seismic sequence.

## Walk-forward validation matrix

The Replay page can validate multiple magnitude thresholds and future
horizons. Each scenario records:

- temporal cutoffs;
- observed outcomes;
- raw family score;
- expanding isotonic calibration;
- empirical and Poisson baselines;
- Brier Score;
- Brier Skill Score;
- expected calibration error;
- precision, recall and false-alarm rate.

The pipeline also supports:

```cmd
python -m src.pipeline validate-grid --catalogue-mode complete
python -m src.pipeline validate-grid --catalogue-mode declustered
```

## Gold build and memory control

Complete and declustered Gold fingerprints are intentionally built in separate
Python processes to keep memory bounded on Windows:

```cmd
python -m src.pipeline build-gold --catalogue-mode complete
python -m src.pipeline build-gold --catalogue-mode declustered
python -m src.pipeline merge-gold
```

The supplied `build_gold_all.cmd` executes this sequence.

## Remaining scientific limitations

The following work remains necessary before formal scientific use:

- review the magnitude-conversion policy;
- benchmark the pilot declustering against established methods;
- validate the bootstrap block length;
- test sensitivity to tectonic-domain polygons;
- evaluate model skill across independent regions;
- obtain formal review from a seismologist;
- avoid operational risk communication without institutional governance.
