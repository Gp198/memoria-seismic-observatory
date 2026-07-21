# Scientific scope

## Research question

Can recurrent, explainable seismic states be identified within Portuguese tectonic domains, and can those state analogues improve probabilistic understanding beyond a simple historical-rate baseline?

## Pilot domains

1. Southwest Iberian Margin.
2. Lower Tagus Valley.

These were selected because they represent distinct tectonic contexts and are associated with major historical Portuguese earthquake hazard. The polygons included in the repository are analytical pilot boundaries, not official source-zone definitions.

## Product outputs

The MVP produces:

- a harmonised event catalogue;
- regional rolling fingerprints;
- historical percentiles;
- nearest prior state analogues;
- feature-level similarity explanations;
- leakage-safe replay evaluations;
- outcome frequencies for defined future horizons;
- data-quality and catalogue-completeness indicators.

## Explicit exclusions

The system does not:

- predict an exact earthquake time;
- declare a large earthquake imminent;
- replace IPMA products;
- issue public alerts;
- infer tectonic stress directly from catalogue counts;
- treat historical and modern catalogue detection as equivalent;
- use a generative model as the scientific decision engine.

## Initial targets

The first evaluation targets are deliberately moderate because large events are too rare for reliable supervised learning:

- event M≥3 within 7 days;
- event M≥4 within 30 days;
- event M≥4 within 90 days;
- maximum observed magnitude within 365 days;
- return to regional baseline.

M≥6 and M≥7 outcomes remain historical descriptive analyses until sufficient validation exists.

## Success criteria

The MVP is scientifically useful when it can demonstrate:

- complete provenance for every event;
- reproducible transformations;
- no future-data leakage;
- calibrated probabilities;
- explicit false-alarm reporting;
- performance compared with naive baselines;
- stable results under reasonable parameter changes;
- clear uncertainty communication.
