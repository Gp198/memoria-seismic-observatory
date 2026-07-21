# MEMÓRIA v0.2.0 — Scientific comparability and baseline revision

## Comparable epochs

| Epoch | Years | Pilot magnitude floor |
|---|---:|---:|
| Historical pre-instrumental | 1000–1899 | M5.0 |
| Early instrumental | 1900–1963 | M4.0 |
| Modern instrumental network | 1964–2007 | M3.0 |
| Contemporary instrumental period | 2008–present | M1.5 |

The effective threshold for each domain and epoch is the maximum between the
transparent pilot floor and the data-driven magnitude of completeness. Current
percentiles use only prior windows from the same epoch and only events above
the common threshold.

These boundaries and floors are pilot operational choices and require
seismologist review before scientific publication.

## Compatibility

Compatibility combines quality, completeness, threshold, field coverage and
source composition. Each component is displayed in the application.

## Temporal families

Nearby windows are grouped into temporal families before nearest-state
selection. Only one representative per family is returned.

## Replay baselines

The empirical and Poisson baselines use exactly the same epoch, exposure,
domain, threshold, cutoff and horizon. Lambda, exposure, event count and
empirical window counts are visible in the interface.

## Map

The map title explicitly shows `Eventos M ≥ X` and the mapped/total count.
