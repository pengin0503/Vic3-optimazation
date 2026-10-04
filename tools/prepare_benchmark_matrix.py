#!/usr/bin/env python3
"""Create a deterministic Victoria 3 benchmark run matrix without measured data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BUILD = {
    "game_version": "1.14.5",
    "caligula_branch": "release/1.14.5",
    "caligula_rev": "9f8281a37e85639359b3b0c2c5df0196e975ca4b",
    "clausewitz_branch": "caligula/release/1.14.x",
    "clausewitz_rev": "fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef",
    "victoria3_exe_sha256": "9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
VARIANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class Error(RuntimeError):
    pass


def parse_threads(value: str) -> list[int]:
    try:
        parts = [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("threads must be comma-separated positive integers") from exc
    if not parts or any(x < 1 for x in parts):
        raise argparse.ArgumentTypeError("threads must be comma-separated positive integers")
    if len(set(parts)) != len(parts):
        raise argparse.ArgumentTypeError("threads must not contain duplicates")
    return parts


def validate_date(value: str | None, name: str) -> None:
    if value is not None and not DATE_RE.fullmatch(value):
        raise Error(f"{name} must use YYYY-MM-DD")


def ensure_empty_root(root: Path) -> None:
    if root.exists() and any(root.iterdir()):
        raise Error(f"output directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)


def manifest_template(
    *,
    run_id: str,
    variant: str,
    repeat: int | None,
    warmup: bool,
    threads: int,
    start_date: str | None,
    end_date: str | None,
    save_filename: str | None,
    save_sha256: str | None,
    country: str | None,
    cpu: str | None,
    pop_consolidation: str = "moderate_consolidation",
) -> dict:
    return {
        "format_version": 1,
        "run_id": run_id,
        "variant": variant,
        "repeat": repeat,
        "warmup": warmup,
        "task_thread_count": threads,
        "wall_clock_seconds": None,
        "ticktask_csv": "ticktask_timings.csv",
        "game_speed": 5,
        "start_date": start_date,
        "end_date": end_date,
        "build": dict(BUILD),
        "game_rules": {
            "pop_consolidation": pop_consolidation,
        },
        "save": {
            "filename": save_filename,
            "sha256": save_sha256,
            "country": country,
            "in_game_date_at_load": start_date,
        },
        "environment": {
            "cpu": cpu,
            "os": "Windows 11",
            "power_plan": None,
            "mods": [],
            "dlc": None,
            "graphics": None,
            "resolution": None,
            "vsync_or_frame_cap": None,
            "camera_state": None,
            "ui_state": None,
            "process_launch_state": None,
        },
        "notes": "",
    }


def create_matrix(
    root: Path,
    *,
    variant: str,
    threads: list[int],
    repeats: int,
    include_warmup: bool,
    start_date: str | None,
    end_date: str | None,
    save_filename: str | None,
    save_sha256: str | None,
    country: str | None,
    cpu: str | None,
    pop_consolidation: str = "moderate_consolidation",
) -> dict:
    if not VARIANT_RE.fullmatch(variant):
        raise Error("variant may contain only letters, digits, dot, underscore, and hyphen")
    if repeats < 1:
        raise Error("repeats must be at least 1")
    validate_date(start_date, "start_date")
    validate_date(end_date, "end_date")
    if start_date and end_date and end_date <= start_date:
        raise Error("end_date must be later than start_date")
    if save_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", save_sha256):
        raise Error("save_sha256 must be a 64-character hexadecimal SHA-256")

    ensure_empty_root(root)
    runs: list[dict] = []

    for thread_count in threads:
        specs: list[tuple[str, int | None, bool]] = []
        if include_warmup:
            specs.append((f"{variant}-t{thread_count:02d}-warmup", None, True))
        specs.extend(
            (f"{variant}-t{thread_count:02d}-r{repeat:02d}", repeat, False)
            for repeat in range(1, repeats + 1)
        )
        for run_id, repeat, warmup in specs:
            run_dir = root / run_id
            run_dir.mkdir()
            template = manifest_template(
                run_id=run_id,
                variant=variant,
                repeat=repeat,
                warmup=warmup,
                threads=thread_count,
                start_date=start_date,
                end_date=end_date,
                save_filename=save_filename,
                save_sha256=save_sha256,
                country=country,
                cpu=cpu,
                pop_consolidation=pop_consolidation,
            )
            (run_dir / "manifest.template.json").write_text(
                json.dumps(template, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            runs.append(
                {
                    "run_id": run_id,
                    "task_thread_count": thread_count,
                    "repeat": repeat,
                    "warmup": warmup,
                    "directory": run_id,
                }
            )

    matrix = {
        "format_version": 1,
        "variant": variant,
        "threads": threads,
        "measured_repeats_per_thread": repeats,
        "warmup_per_thread": include_warmup,
        "start_date": start_date,
        "end_date": end_date,
        "run_count": len(runs),
        "runs": runs,
    }
    (root / "matrix.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return matrix


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--variant", default="vanilla")
    parser.add_argument("--threads", type=parse_threads, default=parse_threads("1,2,4,6,8,12,16"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--save-filename")
    parser.add_argument("--save-sha256")
    parser.add_argument("--country")
    parser.add_argument("--cpu", default="AMD Ryzen 7 9700X")
    parser.add_argument(
        "--pop-consolidation",
        choices=[
            "no_consolidation",
            "minor_consolidation",
            "moderate_consolidation",
            "aggressive_consolidation",
        ],
        default="moderate_consolidation",
    )
    args = parser.parse_args(argv)
    try:
        matrix = create_matrix(
            args.output,
            variant=args.variant,
            threads=args.threads,
            repeats=args.repeats,
            include_warmup=not args.no_warmup,
            start_date=args.start_date,
            end_date=args.end_date,
            save_filename=args.save_filename,
            save_sha256=args.save_sha256,
            country=args.country,
            cpu=args.cpu,
            pop_consolidation=args.pop_consolidation,
        )
    except (Error, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"created {matrix['run_count']} run templates under {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
