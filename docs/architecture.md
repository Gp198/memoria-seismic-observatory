# Architecture

```text
Official and local sources
        │
        ├── IPMA JSON
        ├── ISC FDSN CSV
        ├── AHEAD/EPICA WFS GeoJSON
        └── Historical IPMA CSV
        │
        ▼
Bronze — immutable timestamped responses + SHA-256
        │
        ▼
Source normalisers
        │
        ▼
Silver — common event schema
        │
        ├── duplicate grouping
        ├── preferred-record selection
        ├── quality scoring
        └── tectonic-domain classification
        │
        ▼
Gold — rolling seismic-state fingerprints
        │
        ├── historical percentiles
        ├── nearest-state retrieval
        ├── feature-level explanation
        └── Replay Portugal outcomes
        │
        ▼
Streamlit dashboard + Markdown report
```

## Design principles

- Immutable raw data.
- Explicit provenance.
- Reproducible transformations.
- No silent magnitude conversion.
- Domain-specific analysis.
- Leakage-safe temporal validation.
- Experimental outputs clearly separated from official alerts.
