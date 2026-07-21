# MEMÓRIA v0.5.0 — Scientific integrity and rare-event validation

## Declustering reconciliation

Every preferred event receives one explicit state: background/mainshock,
associated event, or ineligible. Ineligible events preserve a reason such as
missing date, coordinates or magnitude. The dashboard must reconcile to zero.

## Magnitude policies

- **Operational:** includes transparent, unvalidated identity fallbacks.
- **Validated:** includes only reviewed Mw identities or approved/reviewed
  conversions. This policy may have low coverage until a seismologist approves
  conversion relationships.

Gold fingerprints are built for both catalogue modes and both magnitude
policies. Results from different policies must not be mixed.

## Rare-event validation

Classification is evaluated at 0.5%, 1%, 2%, 5% and 10%, not at an unsuitable
50% threshold. Precision–Recall curves and average precision are reported.

## Calibration sufficiency

Isotonic calibration remains experimental until it has at least 30 calibrated
cuts and 5 positive outcomes. Reliability bins display Wilson 95% confidence
intervals, sample size and observed events.

## Communication limits

Operational magnitude results are sensitivity analyses, not homogeneous Mw
catalogue results. The platform does not issue alerts and does not forecast the
certain date, place or magnitude of an earthquake.
