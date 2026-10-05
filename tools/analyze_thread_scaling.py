#!/usr/bin/env python3
"""Analyze TaskThreadCount scaling from an analyze_benchmarks.py report."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


class Error(RuntimeError):
    pass


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Error(f"failed to read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise Error("expected benchmark report JSON object")
    return value


def effective_serial_fraction(speedup: float, threads: int) -> float | None:
    if threads <= 1 or speedup <= 0:
        return None
    denominator = 1.0 - 1.0 / threads
    if denominator == 0:
        return None
    return (1.0 / speedup - 1.0 / threads) / denominator


def analyze(report: dict, plateau_threshold: float = 0.05) -> dict:
    if not 0 <= plateau_threshold < 1:
        raise Error("plateau_threshold must be in [0, 1)")

    variants = []
    for variant in sorted({g.get("variant") for g in report.get("groups", [])}):
        groups = sorted(
            [g for g in report.get("groups", []) if g.get("variant") == variant],
            key=lambda g: g["task_thread_count"],
        )
        if not groups:
            continue
        base = next((g for g in groups if g["task_thread_count"] == 1), groups[0])
        base_threads = base["task_thread_count"]
        base_wall = base["wall_clock_seconds"]["median"]
        if not isinstance(base_wall, (int, float)) or base_wall <= 0:
            raise Error(f"invalid base wall time for variant {variant!r}")

        rows = []
        previous = None
        first_plateau = None
        for group in groups:
            threads = group["task_thread_count"]
            wall = group["wall_clock_seconds"]["median"]
            speedup = base_wall / wall
            variance = group.get('wall_clock_seconds', {}).get('cv')
            variance_known = isinstance(variance, (int, float)) and math.isfinite(variance) and variance >= 0
            noisy = group.get('wall_clock_seconds', {}).get('noisy') if variance_known else None
            row = {
                "task_thread_count": threads,
                "median_wall_clock_seconds": wall,
                "speedup_vs_base": speedup,
                "base_task_thread_count": base_threads,
                "parallel_efficiency_vs_1_thread": (
                    speedup / threads if base_threads == 1 else None
                ),
                "amdahl_effective_serial_fraction": (
                    effective_serial_fraction(speedup, threads)
                    if base_threads == 1
                    else None
                ),
                "wall_clock_noisy": noisy,
                "repeatability_assessed": (
                    isinstance(group.get('runs'), int) and group['runs'] >= 3
                    and noisy is not None
                    and group['wall_clock_seconds'].get('repeatability_assessed', True)
                ),
            }
            if previous is not None:
                prev_wall = previous["median_wall_clock_seconds"]
                improvement = (prev_wall - wall) / prev_wall
                row["incremental_improvement_fraction"] = improvement
                row["speedup_vs_previous"] = prev_wall / wall
                plateau = None
                if row['repeatability_assessed'] and previous['repeatability_assessed']:
                    plateau = (improvement < plateau_threshold
                               and row['wall_clock_noisy'] is False
                               and previous['wall_clock_noisy'] is False)
                row["plateau_screen"] = plateau
                if plateau and first_plateau is None:
                    first_plateau = threads
            else:
                row["incremental_improvement_fraction"] = None
                row["speedup_vs_previous"] = None
                row["plateau_screen"] = None
            rows.append(row)
            previous = row

        variants.append(
            {
                "variant": variant,
                "base_task_thread_count": base_threads,
                "plateau_threshold": plateau_threshold,
                "first_plateau_screen_thread_count": first_plateau,
                "rows": rows,
            }
        )

    if not variants:
        raise Error("benchmark report contains no groups")

    return {
        "format_version": 2,
        "variants": variants,
        "warning": (
            "Amdahl-style serial fraction is a diagnostic model only. "
            "TaskThreadCount does not represent every Victoria 3 thread, and "
            "scheduler, lock, memory, and dependency effects violate ideal "
            "Amdahl assumptions. Plateau flags are screening hints, not causes. "
            "Unknown/insufficient repeatability never establishes a plateau."
        ),
    }


def pct(value):
    return "n/a" if value is None else f"{value * 100:.2f}%"


def markdown(result: dict) -> str:
    lines = [
        "# Victoria 3 TaskThreadCount scaling diagnostics",
        "",
        "> " + result["warning"],
    ]
    for variant in result["variants"]:
        lines += [
            "",
            f"## {variant['variant']}",
            "",
            "| Threads | Median wall (s) | Speedup | Efficiency | Effective serial fraction | Improvement vs previous | Plateau screen |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for row in variant["rows"]:
            efficiency = row["parallel_efficiency_vs_1_thread"]
            serial = row["amdahl_effective_serial_fraction"]
            improvement = row["incremental_improvement_fraction"]
            lines.append(
                f"| {row['task_thread_count']} | {row['median_wall_clock_seconds']:.3f} | "
                f"{row['speedup_vs_base']:.3f}x | {pct(efficiency)} | "
                f"{pct(serial)} | {pct(improvement)} | "
                f"{'unknown' if row['plateau_screen'] is None else ('yes' if row['plateau_screen'] else 'no')} |"
            )
        if variant["first_plateau_screen_thread_count"] is not None:
            lines += [
                "",
                f"First plateau-screen point: **{variant['first_plateau_screen_thread_count']} task threads**.",
            ]
        lines += [
            "",
            "A plateau should trigger WPR/uProf and TickTask dependency/lock analysis; it does not justify forcing additional workers.",
        ]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--plateau-threshold", type=float, default=0.05)
    parser.add_argument("--json", dest="json_output", type=Path)
    parser.add_argument("--markdown", dest="markdown_output", type=Path)
    args = parser.parse_args(argv)

    try:
        result = analyze(load_json(args.report), args.plateau_threshold)
    except (Error, OSError, ZeroDivisionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(markdown(result), encoding="utf-8")
    if not args.json_output and not args.markdown_output:
        sys.stdout.write(markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
