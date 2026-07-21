# MEMÓRIA v0.1.7 — Scientific MVP refinement

## Similarity

- RobustScaler replaces StandardScaler.
- Historical features are winsorised at 2.5% and 97.5%.
- Extreme robust scores are bounded.
- Feature weights are explicit and documented in code.
- Quality and catalogue completeness generate a comparability score.
- Similarity uses adjusted distance rather than raw geometric distance.
- Returned analogues are independent episodes separated by a configurable gap.
- Feature contributions are normalised to 100%.

## Replay Portugal

- Uses independent historical episodes.
- Analogue voting is weighted by similarity and data comparability.
- Tables use Portuguese labels, dates, percentages and outcomes.

## Catalogue quality

- Separates raw records, consolidated events, redundant records and duplicate groups.
- Shows the consolidation rate.
- Adds a source pipeline panel for IPMA, AHEAD and ISC.
- Distinguishes integrated, collected and missing sources.
- Shows the recommended next action for each source.

## User interface

- Technical field names were removed from visible tables.
- Dates and units are formatted consistently.
- The similarity chart now explains percentage contribution instead of displaying unstable raw scores.
