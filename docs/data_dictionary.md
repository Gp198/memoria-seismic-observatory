# Data dictionary

## Silver event catalogue

| Field | Type | Description |
|---|---|---|
| `event_id_memoria` | string | Stable internal event identifier. |
| `source_event_id` | string | Event identifier supplied by the source. |
| `source` | string | IPMA, ISC, AHEAD, IPMA_HISTORICAL or DEMO. |
| `origin_time_utc` | datetime UTC | Preferred origin time. |
| `latitude` | float | Latitude in decimal degrees. |
| `longitude` | float | Longitude in decimal degrees. |
| `depth_km` | float nullable | Hypocentral depth. |
| `magnitude_value` | float nullable | Source magnitude value. |
| `magnitude_type` | string nullable | ML, Mw, mb, Ms or source-specific type. |
| `magnitude_comparable` | float nullable | Analysis magnitude after an explicitly documented conversion. V0.1 normally retains the source value. |
| `intensity_max` | string nullable | Maximum macroseismic intensity when available. |
| `location_text` | string nullable | Source location label. |
| `felt` | boolean nullable | Whether the event was reported as felt. |
| `location_uncertainty_km` | float nullable | Source location uncertainty. |
| `magnitude_uncertainty` | float nullable | Source magnitude uncertainty. |
| `tectonic_domain` | string | Analytical pilot domain. |
| `domain_confidence` | float | Confidence in polygon-based domain assignment. |
| `historical_quality` | string | High, medium, low or unknown. |
| `quality_score` | float | Normalised analytical quality from 0 to 1. |
| `record_status` | string | Preliminary, reviewed, historical or demo. |
| `source_url` | string nullable | Original service or source URL. |
| `source_file` | string | Bronze source path. |
| `duplicate_group_id` | string nullable | Group assigned to probable duplicate records. |
| `is_preferred_record` | boolean | Record selected as the preferred representation of a duplicate group. |
| `ingested_at_utc` | datetime UTC | Ingestion timestamp. |

## Gold fingerprint table

| Field | Description |
|---|---|
| `tectonic_domain` | Domain analysed. |
| `window_days` | Rolling-window length. |
| `window_start` | Inclusive start. |
| `window_end` | Inclusive analytical cutoff. |
| `event_count` | Events above the selected completeness threshold. |
| `event_rate_per_30d` | Count standardised to 30 days. |
| `maximum_magnitude` | Maximum comparable magnitude. |
| `mean_magnitude` | Mean comparable magnitude. |
| `median_depth_km` | Median depth. |
| `depth_std_km` | Depth variability. |
| `spatial_dispersion_km` | Median epicentral distance from the window centroid. |
| `log10_total_energy_j` | Logarithm of summed empirical seismic energy. |
| `days_since_previous_m3` | Days since a prior event M≥3 at the cutoff. |
| `catalogue_completeness_mc` | Estimated regional/epoch magnitude of completeness. |
| `data_quality_score` | Mean quality score in the window. |
| `historical_percentile_event_rate` | Percentile relative to prior windows. |

## Validation and uncertainty fields — v0.3.0

| Field | Layer | Description |
|---|---|---|
| `comparable_effective_sample_size` | Gold | Approximate number of independent reference windows after overlap and lag-one autocorrelation correction. |
| `comparable_percentile_ci_lower` | Gold | Lower bound of the 95% Wilson interval for the comparable empirical percentile. |
| `comparable_percentile_ci_upper` | Gold | Upper bound of the 95% Wilson interval for the comparable empirical percentile. |
| `comparable_overlap_factor` | Gold | `ceil(window_days / step_days)` overlap factor used as a conservative bound. |
| `comparable_lag1_autocorrelation` | Gold | Lag-one autocorrelation of prior comparable event rates. |
| `family_start` | Similarity/Replay | Start of the accepted non-overlapping temporal family. |
| `family_end` | Similarity/Replay | End of the accepted non-overlapping temporal family. |
| `family_buffer_days` | Similarity/Replay | Minimum temporal buffer enforced between complete family intervals. |
| `analogue_calibrated_probability` | Replay validation | Expanding isotonic estimate fitted only with earlier replay cutoffs. |
| `brier_analogue_calibrated` | Replay validation | Brier error of the time-safe calibrated analogue estimate. |


## Scientific audit fields — v0.4.0

| Field | Description |
|---|---|
| `magnitude_original_value` | Magnitude value as received from the source. |
| `magnitude_original_type` | Original magnitude scale/type. |
| `magnitude_homogenization_method` | Operational mapping method. |
| `magnitude_conversion_equation` | Auditable equation or fallback statement. |
| `magnitude_conversion_uncertainty` | Conversion/fallback uncertainty. |
| `magnitude_homogenization_status` | Reviewed, review required, unknown or missing. |
| `cluster_id` | Pilot sequence identifier. |
| `cluster_role` | Background, mainshock, associated or redundant record. |
| `is_background_event` | Included in pilot-declustered mode. |
| `declustering_method` | Declustering method identifier. |
| `catalogue_mode` | `complete` or `declustered` Gold population. |

## Scientific integrity fields — v0.5.0

| Field | Layer | Description |
|---|---|---|
| `declustering_eligible` | Silver | Whether the preferred event has date, coordinates and comparable magnitude required by the pilot declustering. |
| `declustering_exclusion_reason` | Silver | Explicit reason for non-eligibility, such as missing date, coordinates or magnitude. |
| `magnitude_policy` | Gold / validation | `operational` or `validated`; fingerprints from different policies must not be mixed. |
| `IC 95% inferior` / `IC 95% superior` | Validation | Wilson confidence interval for the observed frequency in each reliability bin. |
| `Eventos observados` | Validation | Positive outcomes represented in a calibration or Precision–Recall point. |
| `Average precision` | Validation | Area under the Precision–Recall curve, appropriate for rare positive outcomes. |
