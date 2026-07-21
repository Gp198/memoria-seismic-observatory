# ISC ingestion correction — v0.1.8

## Root cause

The old connector requested `format=csv` and parsed comma-separated data.
The FDSN event text output is pipe-delimited and normally starts with:

```text
#EventID|Time|Latitude|Longitude|Depth/Km|...
```

The request succeeded, but the parser did not recognise any event fields and
discarded every row.

## Corrections

- Requests `format=text`.
- Parses the `|` delimiter.
- Supports old and new Bronze snapshots.
- Splits long periods into two-year chunks.
- Saves a manifest with record counts per chunk.
- Adds `isc-diagnostics`.
- Rejects HTML and unrecognised response bodies instead of reporting a false
  successful ingestion with zero records.
