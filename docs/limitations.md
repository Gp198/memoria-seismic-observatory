# Limitations

1. Earthquakes cannot currently be predicted deterministically by date, place and magnitude.
2. The IPMA public recent-event service is a rolling recent feed and is not a complete historical archive.
3. Historical records are incomplete and their uncertainty is larger.
4. Detection thresholds changed materially over time.
5. Magnitude types are not automatically interchangeable.
6. The bundled demonstration dataset is synthetic.
7. Pilot tectonic polygons are approximate and require expert review.
8. Nearest historical analogues do not imply a causal mechanism.
9. Apparent clusters may reflect aftershocks, network changes or catalogue artefacts.
10. The current baseline is not a production ETAS implementation.
11. Large Portuguese earthquakes are too rare for conventional machine-learning validation.
12. Dashboard language is experimental and must not be interpreted as an IPMA or civil-protection warning.
13. External services can revise records, impose limits or change formats.
14. A public deployment must include provider attribution and licensing review.


## v0.3.0 uncertainty limitations

The reported effective sample size is a conservative approximation based on overlap and lag-one autocorrelation. Family width, buffers and calibration thresholds are pilot settings. See `docs/validation_v0.3.0.md`.


## v0.4.0 scientific-sensitivity limitations

The pilot declustering layer is a transparent space-time sensitivity method,
not an official Gardner–Knopoff, Reasenberg or ETAS implementation. Non-Mw
magnitudes without a reviewed conversion policy remain on an explicitly
flagged operational fallback scale. Moving-block bootstrap intervals depend on
the selected block length and do not replace a full seismic point-process
model. Adaptive temporal regimes are change-point heuristics and must not be
interpreted as physically proven fault states.

## v0.5.0 scientific-integrity limitations

The validated magnitude policy may contain very few events until conversion
relationships are approved by a seismologist. Operational results that use
unvalidated identity fallbacks are sensitivity analyses and must not be
presented as a homogeneous Mw catalogue. Precision–Recall and decision metrics
remain unstable when the number of positive replay outcomes is small. Isotonic
calibration is labelled experimental until at least 30 calibrated cutoffs and
five positive outcomes are available. Declustering-ineligible events remain in
the consolidated catalogue but are excluded from the pilot declustered
population with an explicit reason.
