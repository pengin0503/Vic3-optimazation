#!/usr/bin/env python3
"""Finalize one Victoria 3 benchmark run after its TickTask CSV is captured."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

REQ = {"frame", "task", "milliseconds", "calls", "longest_lock"}


class Error(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_ticktask_csv(path: Path) -> int:
    if not path.is_file():
        raise Error(f"missing TickTask CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = REQ - set(reader.fieldnames or ())
        if missing:
            raise Error(f"TickTask CSV is missing columns: {', '.join(sorted(missing))}")
        rows = 0
        for rows, row in enumerate(reader, 1):
            if not (row.get("task") or "").strip():
                raise Error(f"TickTask CSV row {rows + 1} has an empty task")
        if rows == 0:
            raise Error("TickTask CSV contains no data rows")
        return rows


def finalize(run_dir: Path, wall_clock_seconds: float, notes: str | None = None) -> dict:
    if not math.isfinite(wall_clock_seconds) or wall_clock_seconds <= 0:
        raise Error("wall_clock_seconds must be a positive finite number")
    template_path = run_dir / "manifest.template.json"
    output_path = run_dir / "manifest.json"
    if output_path.exists():
        raise Error(f"manifest already exists: {output_path}")
    if not template_path.is_file():
        raise Error(f"missing manifest template: {template_path}")
    try:
        manifest = json.loads(template_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Error(f"invalid manifest template: {exc}") from exc

    csv_name = manifest.get("ticktask_csv", "ticktask_timings.csv")
    csv_path = run_dir / csv_name
    row_count = validate_ticktask_csv(csv_path)

    manifest["wall_clock_seconds"] = wall_clock_seconds
    if notes is not None:
        manifest["notes"] = notes
    manifest["capture"] = {
        "ticktask_csv_sha256": sha256_file(csv_path),
        "ticktask_csv_size_bytes": csv_path.stat().st_size,
        "ticktask_csv_rows": row_count,
    }
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--wall-clock-seconds", type=float, required=True)
    parser.add_argument("--notes")
    args = parser.parse_args(argv)
    try:
        manifest = finalize(args.run_dir, args.wall_clock_seconds, args.notes)
    except (Error, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"finalized {manifest['run_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
