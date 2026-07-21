# MEMÓRIA v0.3.0 — Validation and uncertainty release

## 1. Non-overlapping temporal families

Historical states are ranked by robust distance, but the final analogue set is
constructed as temporal families rather than isolated rolling windows.

For each representative window, MEMÓRIA creates a family interval around the
representative. A family is accepted only when its complete interval is
separated from every previously selected family by an explicit buffer.
Therefore, the selection rule is applied to family intervals, not only to
representative dates.

The interface reports:

- family interval;
- representative window;
- rolling windows grouped in the family;
- family width;
- separation buffer.

## 2. Effective sample size

Rolling windows are highly dependent because adjacent windows share most of
their observations. MEMÓRIA therefore reports both:

- the number of rolling reference windows;
- an approximate effective sample size.

The effective sample size is conservatively bounded by:

1. the number of rolling windows;
2. the non-overlapping-window equivalent `n / ceil(window_days / step_days)`;
3. an AR(1) autocorrelation correction when lag-one correlation is positive.

A 95% Wilson interval is calculated using the effective sample size. The
interval quantifies uncertainty in the empirical percentile; it is not a
confidence interval for earthquake occurrence.

## 3. Archive memory versus comparable memory

The interface separates:

- total archive span;
- statistically comparable reference span.

The full archive remains available for historical context, quality analysis
and epoch-specific research, but the current percentile uses only the target
observation epoch.

## 4. Segmented fingerprint history

The fingerprint history is rendered as independent epoch segments. Each
segment displays its own comparison magnitude threshold. Lines are not joined
across epoch boundaries.

Users can switch between:

- comparable event rate;
- raw catalogue event rate.

The raw rate is explicitly described as catalogue coverage, not a direct
physical measure of seismic activity.

## 5. Analogue score and calibration

The weighted proportion of historical families with a future event is labelled
as an **uncalibrated family score**, not automatically as a probability.

Walk-forward validation calculates:

- mean Brier score;
- Brier Skill Score against empirical and Poisson baselines;
- temporal calibration curves;
- precision, recall and false-alarm rate at a configurable decision threshold;
- expanding isotonic calibration.

For each cutoff, isotonic calibration is fitted only with earlier cutoffs.
No future replay outcomes are used to calibrate a previous forecast.

## 6. Map scalability

The map supports:

- density mode;
- clustered-point mode;
- individual-point mode.

Density is the default for large event sets. The analytical catalogue is not
sampled or reduced; only its visual representation changes.

## Scientific limitations

The effective sample size is an approximation. The epoch boundaries,
comparison floors, family width and decision threshold remain pilot choices.
They require review by a seismologist and sensitivity analysis before formal
scientific publication or operational use.
