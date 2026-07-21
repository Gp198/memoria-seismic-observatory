# ISC timeout resilience — v0.1.9

Modern ISC queries can contain many more records than older periods. A large
rectangular query may exceed the provider response time even though the API and
network are working normally.

Version 0.1.9 adds:

- six-month initial chunks instead of two-year chunks;
- a 120-second ISC read timeout;
- retry with exponential backoff;
- automatic binary splitting of slow chunks down to seven days;
- checkpoints and automatic resume from successful Bronze files;
- a manifest marked `complete`, `partial`, or `failed`;
- an explicit error when any final interval is missing;
- optional `--continue-on-error` for exploratory partial ingestion.

Recommended command:

```cmd
python -m src.pipeline ingest-isc --start 2008-01-01 --end 2026-12-31 --min-lat 32 --max-lat 44 --min-lon -20 --max-lon -5 --chunk-months 3 --read-timeout 120 --max-retries 1
```

If the provider remains slow, rerun the same command. Completed ranges are read
from Bronze and are not downloaded again.

More conservative mode:

```cmd
python -m src.pipeline ingest-isc --start 2008-01-01 --end 2026-12-31 --min-lat 32 --max-lat 44 --min-lon -20 --max-lon -5 --chunk-months 1 --min-chunk-days 3 --read-timeout 180 --max-retries 2
```
