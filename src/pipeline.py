from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.config import PATHS, load_settings
from src.demo import generate_demo_events
from src.features.fingerprints import (
    build_fingerprints,
    build_fingerprints_all_modes,
)
from src.geography.tectonic_domains import classify_events
from src.http_client import request_diagnostics
from src.ingestion.ahead import fetch_ahead_epica, normalise_ahead_payload
from src.ingestion.ipma import ingest_ipma_areas, normalise_ipma_payload
from src.ingestion.isc import (
    diagnose_isc_bronze_file,
    fetch_isc_events,
    normalise_isc_response,
)
from src.quality.deduplication import deduplicate_events
from src.quality.declustering import annotate_declustering
from src.quality.magnitude import homogenize_magnitudes
from src.reporting.explanations import generate_markdown_report
from src.schema import concatenate_events, ensure_event_schema
from src.storage import (
    load_dataframe,
    load_silver_events,
    remove_derived_outputs,
    save_dataframe,
    save_gold_fingerprints,
    save_silver_events,
)


def _load_bronze_frames() -> list[pd.DataFrame]:
    frames: list[pd.DataFrame] = []

    for path in PATHS.bronze.rglob("*.json"):
        if path.name.endswith(".sha256"):
            continue

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue

        lowered = str(path).lower()

        if "/ipma/" in lowered or "\\ipma\\" in lowered:
            frames.append(
                normalise_ipma_payload(payload, str(path))
            )

        elif "/ahead/" in lowered or "\\ahead\\" in lowered:
            frames.append(
                normalise_ahead_payload(payload, str(path))
            )

        elif "/isc/" in lowered or "\\isc\\" in lowered:
            if not isinstance(payload, dict):
                continue

            response_text = (
                payload.get("response_text")
                or payload.get("response_csv")
            )
            if not response_text:
                continue

            try:
                frames.append(
                    normalise_isc_response(
                        response_text,
                        source_file=str(path),
                        source_url=payload.get(
                            "response_url",
                            "",
                        ),
                    )
                )
            except ValueError as error:
                print(
                    f"WARNING: ISC Bronze ignorado "
                    f"({path.name}): {error}"
                )

    for path in PATHS.bronze.rglob("*.csv"):
        if (
            "normalised" in path.stem.lower()
            or "normalized" in path.stem.lower()
        ):
            continue

        try:
            raw = pd.read_csv(path)
        except Exception:
            continue

        required = {"event_id_memoria", "origin_time_utc"}
        if required.issubset(raw.columns):
            frames.append(ensure_event_schema(raw))

    return frames


def build_silver() -> pd.DataFrame:
    settings = load_settings()
    frames = _load_bronze_frames()

    if not frames:
        raise RuntimeError(
            "No Bronze source data were found. "
            "Run an ingestion command or bootstrap-demo."
        )

    events = concatenate_events(frames)
    events = homogenize_magnitudes(events)
    events = deduplicate_events(
        events,
        time_seconds=settings["duplicate_time_seconds"],
        distance_km=settings["duplicate_distance_km"],
        magnitude_delta=settings["duplicate_magnitude_delta"],
    )
    events = classify_events(events)
    events = annotate_declustering(events)
    save_silver_events(events)
    return events


def _real_bronze_exists() -> bool:
    for source in ("ipma", "isc", "ahead"):
        folder = PATHS.bronze / source
        if folder.exists() and any(folder.rglob("*.json")):
            return True
    return False


def _assert_silver_is_not_stale_demo(
    events: pd.DataFrame,
) -> None:
    sources = set(
        events["source"].dropna().astype(str).unique()
    )
    if sources and sources <= {"DEMO"} and _real_bronze_exists():
        raise RuntimeError(
            "The Silver catalogue still contains only DEMO data "
            "while real Bronze snapshots exist. Run "
            "`python -m src.pipeline clean-derived` followed by "
            "`python -m src.pipeline build-silver`."
        )


def merge_gold_fingerprints() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for catalogue_mode in ("complete", "declustered"):
        for magnitude_policy in ("operational", "validated"):
            base = PATHS.gold / f"fingerprints_{catalogue_mode}_{magnitude_policy}"
            if base.with_suffix(".csv").exists() or base.with_suffix(".parquet").exists():
                try:
                    frame = load_dataframe(base)
                except pd.errors.EmptyDataError:
                    continue
                if not frame.empty:
                    frames.append(frame)
    if not frames:
        raise FileNotFoundError(
            "No per-mode Gold fingerprints exist. Build at least one catalogue mode."
        )
    fingerprints = pd.concat(frames, ignore_index=True)
    save_gold_fingerprints(fingerprints)
    return fingerprints


def build_gold(
    events: pd.DataFrame | None = None,
    catalogue_mode: str = "complete",
    magnitude_policy: str = "operational",
) -> pd.DataFrame:
    source_events = events if events is not None else load_silver_events()
    _assert_silver_is_not_stale_demo(source_events)
    fingerprints = build_fingerprints(
        source_events,
        window_days=(30, 90, 365),
        step_days=7,
        catalogue_mode=catalogue_mode,
        magnitude_policy=magnitude_policy,
    )
    if fingerprints.empty and len(fingerprints.columns) == 0:
        fingerprints = pd.DataFrame(
            columns=[
                "catalogue_mode",
                "magnitude_policy",
                "tectonic_domain",
                "window_days",
                "window_start",
                "window_end",
            ]
        )
    save_dataframe(
        fingerprints,
        PATHS.gold / f"fingerprints_{catalogue_mode}_{magnitude_policy}",
    )
    merge_gold_fingerprints()
    return fingerprints


def bootstrap_demo() -> tuple[pd.DataFrame, pd.DataFrame]:
    PATHS.ensure()
    events = generate_demo_events()
    events = homogenize_magnitudes(events)
    events = annotate_declustering(events)
    sample_path = PATHS.sample / "demo_events.csv"
    events.to_csv(sample_path, index=False)
    save_silver_events(events)
    frames: list[pd.DataFrame] = []
    for catalogue_mode in ("complete", "declustered"):
        for magnitude_policy in ("operational", "validated"):
            fingerprints = build_fingerprints(
                events,
                window_days=(30, 90, 365),
                step_days=30,
                catalogue_mode=catalogue_mode,
                magnitude_policy=magnitude_policy,
            )
            save_dataframe(
                fingerprints,
                PATHS.gold
                / f"fingerprints_{catalogue_mode}_{magnitude_policy}",
            )
            if not fingerprints.empty:
                frames.append(fingerprints)
    merged = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame()
    )
    save_gold_fingerprints(merged)
    return events, merged


def run_all(
    ipma_areas: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    PATHS.ensure()
    live = ingest_ipma_areas(ipma_areas)

    live_path = (
        PATHS.bronze
        / "ipma"
        / "normalised_latest.csv"
    )
    live_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    live.to_csv(live_path, index=False)

    events = build_silver()
    for catalogue_mode in ("complete", "declustered"):
        for magnitude_policy in ("operational", "validated"):
            build_gold(
                events,
                catalogue_mode=catalogue_mode,
                magnitude_policy=magnitude_policy,
            )
    fingerprints = merge_gold_fingerprints()
    generate_markdown_report(events, fingerprints)
    return events, fingerprints


def _latest_isc_response_file() -> Path:
    candidates = [
        path
        for path in (PATHS.bronze / "isc").rglob("*.json")
        if "manifest_" not in path.name
    ]
    if not candidates:
        raise FileNotFoundError(
            "Não existem respostas ISC na camada Bronze."
        )
    return max(
        candidates,
        key=lambda path: path.stat().st_mtime,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MEMÓRIA data pipeline"
    )
    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sub.add_parser("bootstrap-demo")
    sub.add_parser("build-silver")
    gold = sub.add_parser("build-gold")
    gold.add_argument(
        "--catalogue-mode", choices=["complete", "declustered"], default="complete"
    )
    gold.add_argument(
        "--magnitude-policy", choices=["operational", "validated"], default="operational"
    )
    sub.add_parser("merge-gold")
    sub.add_parser("report")
    sub.add_parser("tls-diagnostics")
    sub.add_parser("clean-derived")
    sub.add_parser("data-status")
    validate_grid = sub.add_parser("validate-grid")
    validate_grid.add_argument("--domain", default="Margem Sudoeste Ibérica")
    validate_grid.add_argument("--window-days", type=int, default=90)
    validate_grid.add_argument("--thresholds", nargs="+", type=float, default=[3.5, 4.0, 4.5, 5.0])
    validate_grid.add_argument("--horizons", nargs="+", type=int, default=[7, 30, 90])
    validate_grid.add_argument("--frequency", default="60D")
    validate_grid.add_argument("--catalogue-mode", choices=["complete", "declustered"], default="complete")
    validate_grid.add_argument("--magnitude-policy", choices=["operational", "validated"], default="operational")

    isc_diag = sub.add_parser("isc-diagnostics")
    isc_diag.add_argument("--file", default=None)

    ipma = sub.add_parser("ingest-ipma")
    ipma.add_argument(
        "--ipma-areas",
        nargs="+",
        type=int,
        default=[7, 3],
    )

    isc = sub.add_parser("ingest-isc")
    isc.add_argument("--start", required=True)
    isc.add_argument("--end", required=True)
    isc.add_argument("--min-lat", type=float, default=32)
    isc.add_argument("--max-lat", type=float, default=44)
    isc.add_argument("--min-lon", type=float, default=-20)
    isc.add_argument("--max-lon", type=float, default=-5)
    isc.add_argument("--min-mag", type=float, default=None)
    isc.add_argument("--chunk-months", type=int, default=6)
    isc.add_argument("--chunk-years", type=int, default=None)
    isc.add_argument("--min-chunk-days", type=int, default=7)
    isc.add_argument("--max-retries", type=int, default=1)
    isc.add_argument("--connect-timeout", type=int, default=20)
    isc.add_argument("--read-timeout", type=int, default=120)
    isc.add_argument("--continue-on-error", action="store_true")

    ahead = sub.add_parser("ingest-ahead")
    ahead.add_argument(
        "--min-mag",
        type=float,
        default=None,
    )

    run = sub.add_parser("run-all")
    run.add_argument(
        "--ipma-areas",
        nargs="+",
        type=int,
        default=[7, 3],
    )

    args = parser.parse_args()
    PATHS.ensure()

    if args.command == "bootstrap-demo":
        events, fingerprints = bootstrap_demo()
        print(
            f"Demo ready: {len(events)} events, "
            f"{len(fingerprints)} fingerprints."
        )

    elif args.command == "ingest-ipma":
        events = ingest_ipma_areas(
            args.ipma_areas
        )
        path = (
            PATHS.bronze
            / "ipma"
            / "normalised_latest.csv"
        )
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        events.to_csv(path, index=False)
        print(
            f"Ingested {len(events)} IPMA records."
        )

    elif args.command == "ingest-isc":
        events, path = fetch_isc_events(
            args.start,
            args.end,
            args.min_lat,
            args.max_lat,
            args.min_lon,
            args.max_lon,
            args.min_mag,
            chunk_months=args.chunk_months,
            chunk_years=args.chunk_years,
            min_chunk_days=args.min_chunk_days,
            max_retries=args.max_retries,
            connect_timeout=args.connect_timeout,
            read_timeout=args.read_timeout,
            continue_on_error=args.continue_on_error,
        )
        normalised = path.with_name(
            path.stem + "_normalised.csv"
        )
        events.to_csv(
            normalised,
            index=False,
        )
        print(
            f"Ingested {len(events)} ISC records "
            f"into {path}."
        )

    elif args.command == "ingest-ahead":
        events, path = fetch_ahead_epica(
            minimum_mw=args.min_mag
        )
        normalised = path.with_name(
            path.stem + "_normalised.csv"
        )
        events.to_csv(
            normalised,
            index=False,
        )
        print(
            f"Ingested {len(events)} "
            f"AHEAD/EPICA records into {path}."
        )

    elif args.command == "build-silver":
        events = build_silver()
        print(
            f"Silver catalogue: "
            f"{len(events)} source records."
        )

    elif args.command == "build-gold":
        fingerprints = build_gold(
            catalogue_mode=args.catalogue_mode,
            magnitude_policy=args.magnitude_policy,
        )
        print(
            f"Gold {args.catalogue_mode}/{args.magnitude_policy}: "
            f"{len(fingerprints)} rows."
        )

    elif args.command == "merge-gold":
        fingerprints = merge_gold_fingerprints()
        print(
            f"Merged Gold fingerprints: {len(fingerprints)} rows."
        )

    elif args.command == "report":
        from src.storage import load_gold_fingerprints

        events = load_silver_events()
        fingerprints = load_gold_fingerprints()
        print(
            generate_markdown_report(
                events,
                fingerprints,
            )
        )

    elif args.command == "tls-diagnostics":
        print(
            json.dumps(
                request_diagnostics(),
                indent=2,
                default=str,
            )
        )

    elif args.command == "clean-derived":
        removed = remove_derived_outputs()
        print(
            f"Removed {len(removed)} "
            "derived files."
        )
        for path in removed:
            print(path)

    elif args.command == "isc-diagnostics":
        diagnostic_path = (
            Path(args.file)
            if args.file
            else _latest_isc_response_file()
        )
        print(
            json.dumps(
                diagnose_isc_bronze_file(
                    diagnostic_path
                ),
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    elif args.command == "validate-grid":
        from src.backtesting.replay import walk_forward_grid
        from src.backtesting.validation import summarise_backtest_grid
        from src.storage import load_gold_fingerprints, save_dataframe

        events = load_silver_events()
        fingerprints = load_gold_fingerprints()
        scores = walk_forward_grid(
            events,
            fingerprints,
            domain=args.domain,
            window_days=args.window_days,
            thresholds=tuple(args.thresholds),
            horizons=tuple(args.horizons),
            frequency=args.frequency,
            family_method="adaptive",
            catalogue_mode=args.catalogue_mode,
            magnitude_policy=args.magnitude_policy,
        )
        if scores.empty:
            print("No validation scores were produced.")
        else:
            summary = summarise_backtest_grid(scores)
            score_base = PATHS.gold / f"validation_scores_{args.catalogue_mode}_{args.magnitude_policy}"
            summary_base = PATHS.gold / f"validation_summary_{args.catalogue_mode}_{args.magnitude_policy}"
            save_dataframe(scores, score_base)
            save_dataframe(summary, summary_base)
            print(
                f"Validation complete: {len(scores)} cuts, "
                f"{len(summary)} model/threshold/horizon summaries."
            )

    elif args.command == "data-status":
        try:
            events = load_silver_events()
            print("Silver catalogue")
            print(f"Rows: {len(events)}")
            print(
                events["source"]
                .astype("string")
                .value_counts(dropna=False)
                .to_string()
            )
            print(
                f"From: "
                f"{events['origin_time_utc'].min()}"
            )
            print(
                f"To:   "
                f"{events['origin_time_utc'].max()}"
            )
        except FileNotFoundError:
            print(
                "Silver catalogue: not built"
            )

        try:
            from src.storage import (
                load_gold_fingerprints,
            )

            gold = load_gold_fingerprints()
            print("\nGold fingerprints")
            print(f"Rows: {len(gold)}")
            if not gold.empty:
                print(
                    gold.groupby(
                        [
                            *(["catalogue_mode"] if "catalogue_mode" in gold.columns else []),
                            *(["magnitude_policy"] if "magnitude_policy" in gold.columns else []),
                            "tectonic_domain",
                            "window_days",
                        ]
                    )
                    .size()
                    .to_string()
                )
        except FileNotFoundError:
            print(
                "\nGold fingerprints: not built"
            )

    elif args.command == "run-all":
        events, fingerprints = run_all(
            args.ipma_areas
        )
        print(
            f"Pipeline complete: "
            f"{len(events)} events, "
            f"{len(fingerprints)} fingerprints."
        )


if __name__ == "__main__":
    main()
