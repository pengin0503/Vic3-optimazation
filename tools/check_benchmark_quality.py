#!/usr/bin/env python3
"""Validate Victoria 3 benchmark run-set integrity before performance analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path


class Error(RuntimeError):
    pass


def _issue(code: str, message: str, *, path: Path | None = None, run_id: str | None = None) -> dict:
    out = {"code": code, "message": message}
    if path is not None:
        out["path"] = path.as_posix()
    if run_id is not None:
        out["run_id"] = run_id
    return out


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise Error(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise Error(f"expected JSON object: {path}")
    return data


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _discover(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise Error(f"benchmark path does not exist: {root}")
    manifests = sorted(root.rglob("manifest.json"), key=lambda p: p.as_posix().lower())
    if not manifests:
        raise Error(f"no manifest.json under {root}")
    return manifests


def _identity(manifest: dict, nested: str, nested_key: str, legacy_key: str | None = None):
    obj = manifest.get(nested)
    if isinstance(obj, dict) and obj.get(nested_key) not in (None, ""):
        return obj.get(nested_key)
    if legacy_key:
        return manifest.get(legacy_key)
    return None


def _csv_expected_hash(manifest: dict):
    capture = manifest.get("capture")
    if isinstance(capture, dict) and capture.get("ticktask_csv_sha256"):
        return capture["ticktask_csv_sha256"]
    return manifest.get("csv_sha256")


def workload_fingerprint(rows: list[tuple[int, str, int]]) -> dict:
    """Deterministic workload identity from (frame, task, calls) rows only.

    Milliseconds and longest_lock are measurements, not workload identity, so
    they never participate. Rows form a multiset: file order is irrelevant but
    duplicate rows are significant.
    """
    digest = hashlib.sha256()
    for frame, task, calls in sorted(rows):
        digest.update(f"{frame}\t{task}\t{calls}\n".encode("utf-8"))
    frames = {frame for frame, _, _ in rows}
    return {
        "row_count": len(rows),
        "frame_count": len(frames),
        "min_frame": min(frames) if frames else None,
        "max_frame": max(frames) if frames else None,
        "fingerprint_sha256": digest.hexdigest(),
    }


def _read_boundary_rows(csv_path: Path) -> list[tuple[int, str, int]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = {"frame", "task", "calls"} - set(reader.fieldnames or ())
        if missing:
            raise Error(f"missing CSV columns: {', '.join(sorted(missing))}")
        rows = []
        for line, row in enumerate(reader, 2):
            task = (row["task"] or "").strip()
            try:
                frame = int(row["frame"])
                calls_value = float(row["calls"])
            except (TypeError, ValueError) as exc:
                raise Error(f"row {line}: invalid frame/calls") from exc
            if not task or not math.isfinite(calls_value) or calls_value < 0 or calls_value != int(calls_value):
                raise Error(f"row {line}: invalid task/calls")
            rows.append((frame, task, int(calls_value)))
    return rows


def _boundary_summary(boundary: dict) -> str:
    return (
        f"frames {boundary['min_frame']}..{boundary['max_frame']} "
        f"({boundary['frame_count']} frames, {boundary['row_count']} rows, "
        f"sha256 {boundary['fingerprint_sha256'][:12]})"
    )


def _load_run(path: Path) -> dict:
    manifest = _read_json(path)
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise Error(f"{path}: missing/invalid run_id")
    threads = manifest.get("task_thread_count")
    if not isinstance(threads, int) or threads < 1:
        raise Error(f"{path}: missing/invalid task_thread_count")
    warmup = bool(manifest.get("warmup", False))
    wall = manifest.get("wall_clock_seconds")
    if wall is not None and (
        not isinstance(wall, (int, float))
        or not math.isfinite(float(wall))
        or wall <= 0
    ):
        raise Error(f"{path}: invalid wall_clock_seconds")
    return {
        "path": path,
        "manifest": manifest,
        "run_id": run_id,
        "variant": manifest.get("variant", "unknown"),
        "threads": threads,
        "repeat": manifest.get("repeat"),
        "warmup": warmup,
        "wall": float(wall) if wall is not None else None,
        "build_hash": _identity(
            manifest, "build", "victoria3_exe_sha256", "executable_sha256"
        ),
        "save_hash": _identity(manifest, "save", "sha256", "save_sha256"),
        "pop": _identity(
            manifest, "game_rules", "pop_consolidation", "pop_consolidation"
        ),
    }


def _compare_consistency(
    runs: list[dict],
    field: str,
    code: str,
    label: str,
    errors: list[dict],
) -> None:
    values = [(r, r[field]) for r in runs if r[field] not in (None, "")]
    distinct = {value for _, value in values}
    if len(distinct) <= 1:
        return
    canonical = values[0][1]
    for run, value in values[1:]:
        if value != canonical:
            errors.append(
                _issue(
                    code,
                    f"{label} differs from first observed value",
                    path=run["path"],
                    run_id=run["run_id"],
                )
            )


def check(
    root: Path,
    *,
    matrix_path: Path | None = None,
    cv_threshold: float = 0.03,
    outlier_fraction: float = 0.10,
) -> dict:
    if cv_threshold < 0:
        raise Error("cv_threshold must be non-negative")
    if outlier_fraction < 0:
        raise Error("outlier_fraction must be non-negative")

    runs = [_load_run(p) for p in _discover(root)]
    errors: list[dict] = []
    warnings: list[dict] = []

    by_id: dict[str, list[dict]] = {}
    for run in runs:
        by_id.setdefault(run["run_id"], []).append(run)
    for run_id, matches in sorted(by_id.items()):
        if len(matches) > 1:
            for run in matches:
                errors.append(
                    _issue(
                        "duplicate_run_id",
                        f"run_id appears {len(matches)} times",
                        path=run["path"],
                        run_id=run_id,
                    )
                )

    _compare_consistency(
        runs,
        "build_hash",
        "build_hash_mismatch",
        "Victoria 3 executable hash",
        errors,
    )
    _compare_consistency(
        runs,
        "save_hash",
        "save_hash_mismatch",
        "save hash",
        errors,
    )
    _compare_consistency(
        runs,
        "pop",
        "pop_consolidation_mismatch",
        "Pop Consolidation setting",
        errors,
    )

    for run in runs:
        manifest = run["manifest"]
        if not run["warmup"] and run["wall"] is None:
            errors.append(
                _issue(
                    "missing_wall_clock",
                    "measured run is missing wall_clock_seconds",
                    path=run["path"],
                    run_id=run["run_id"],
                )
            )
        if run["warmup"] and run["repeat"] is not None:
            errors.append(
                _issue(
                    "warmup_has_repeat",
                    "warm-up run must not occupy a measured repeat number",
                    path=run["path"],
                    run_id=run["run_id"],
                )
            )
        csv_name = manifest.get("ticktask_csv")
        if not isinstance(csv_name, str) or not csv_name:
            errors.append(
                _issue(
                    "missing_ticktask_csv",
                    "ticktask_csv is missing",
                    path=run["path"],
                    run_id=run["run_id"],
                )
            )
            continue
        csv_path = run["path"].parent / csv_name
        if not csv_path.is_file():
            errors.append(
                _issue(
                    "missing_ticktask_csv",
                    f"TickTask CSV does not exist: {csv_name}",
                    path=run["path"],
                    run_id=run["run_id"],
                )
            )
            continue
        try:
            run["boundary"] = workload_fingerprint(_read_boundary_rows(csv_path))
        except (Error, csv.Error, UnicodeError) as exc:
            errors.append(
                _issue(
                    "invalid_ticktask_csv",
                    f"TickTask CSV workload boundary is unreadable: {exc}",
                    path=run["path"],
                    run_id=run["run_id"],
                )
            )
        expected = _csv_expected_hash(manifest)
        if expected:
            actual = _sha256(csv_path)
            if str(expected).lower() != actual:
                errors.append(
                    _issue(
                        "csv_hash_mismatch",
                        (
                            "TickTask CSV SHA-256 mismatch: "
                            f"expected {expected}, got {actual}"
                        ),
                        path=run["path"],
                        run_id=run["run_id"],
                    )
                )

    if matrix_path is not None:
        matrix = _read_json(matrix_path)
        specs = matrix.get("runs")
        if not isinstance(specs, list):
            raise Error(f"{matrix_path}: runs must be an array")
        for spec in specs:
            if not isinstance(spec, dict) or not isinstance(spec.get("run_id"), str):
                raise Error(f"{matrix_path}: invalid run entry")
            run_id = spec["run_id"]
            matches = by_id.get(run_id, [])
            if not matches:
                errors.append(
                    _issue(
                        "missing_run",
                        "expected matrix run is missing",
                        path=matrix_path,
                        run_id=run_id,
                    )
                )
                continue
            if len(matches) != 1:
                continue
            run = matches[0]
            expected_threads = spec.get("task_thread_count")
            if expected_threads is not None and run["threads"] != expected_threads:
                errors.append(
                    _issue(
                        "task_thread_count_mismatch",
                        f"expected {expected_threads}, got {run['threads']}",
                        path=run["path"],
                        run_id=run_id,
                    )
                )
            expected_repeat = spec.get("repeat")
            if run["repeat"] != expected_repeat:
                errors.append(
                    _issue(
                        "repeat_mismatch",
                        (
                            f"expected repeat {expected_repeat!r}, "
                            f"got {run['repeat']!r}"
                        ),
                        path=run["path"],
                        run_id=run_id,
                    )
                )
            expected_warmup = bool(spec.get("warmup", False))
            if run["warmup"] != expected_warmup:
                errors.append(
                    _issue(
                        "warmup_mismatch",
                        (
                            f"expected warmup={expected_warmup}, "
                            f"got {run['warmup']}"
                        ),
                        path=run["path"],
                        run_id=run_id,
                    )
                )

    groups = []
    measured = [
        r for r in runs
        if not r["warmup"] and r["wall"] is not None
    ]
    keyed: dict[tuple[str, int], list[dict]] = {}
    for run in measured:
        keyed.setdefault((str(run["variant"]), run["threads"]), []).append(run)

    for (variant, threads), group_runs in sorted(keyed.items()):
        numeric = [float(r["wall"]) for r in group_runs]
        median = statistics.median(numeric)
        cv = None
        if len(numeric) >= 2:
            mean = statistics.mean(numeric)
            cv = statistics.stdev(numeric) / mean if mean else None

        if len(numeric) < 3:
            warnings.append(
                _issue(
                    "insufficient_repeats",
                    (
                        f"{variant} threads={threads} has {len(numeric)} "
                        "measured run(s); need at least 3"
                    ),
                    run_id=f"{variant}:t{threads}",
                )
            )
        elif cv is not None and cv > cv_threshold:
            warnings.append(
                _issue(
                    "excessive_cv",
                    (
                        f"{variant} threads={threads} wall-clock CV "
                        f"{cv:.4f} exceeds {cv_threshold:.4f}"
                    ),
                    run_id=f"{variant}:t{threads}",
                )
            )

        if len(numeric) >= 3 and median > 0:
            for run in group_runs:
                fraction = abs(float(run["wall"]) - median) / median
                if fraction > outlier_fraction:
                    warnings.append(
                        _issue(
                            "wall_clock_outlier",
                            (
                                "wall clock differs from group median by "
                                f"{fraction:.1%}"
                            ),
                            path=run["path"],
                            run_id=run["run_id"],
                        )
                    )

        groups.append(
            {
                "variant": variant,
                "task_thread_count": threads,
                "runs": len(numeric),
                "median_wall_clock_seconds": median,
                "wall_clock_cv": cv,
            }
        )

    # Every measured run in one report is compared against one workload: thread
    # scaling and profiler enabled/disabled comparisons are only meaningful when
    # each run simulated the same frames/tasks/calls.
    bounded = sorted(
        (r for r in measured if r.get("boundary") is not None),
        key=lambda r: r["run_id"],
    )
    if bounded:
        counts: dict[str, int] = {}
        for run in bounded:
            key = run["boundary"]["fingerprint_sha256"]
            counts[key] = counts.get(key, 0) + 1
        # Reference = most common boundary; ties go to the first run_id.
        reference = max(
            bounded, key=lambda r: counts[r["boundary"]["fingerprint_sha256"]]
        )
        reference_key = reference["boundary"]["fingerprint_sha256"]
        for run in bounded:
            if run["boundary"]["fingerprint_sha256"] != reference_key:
                warnings.append(
                    _issue(
                        "workload_boundary_mismatch",
                        (
                            f"workload boundary {_boundary_summary(run['boundary'])} "
                            f"differs from reference run {reference['run_id']} "
                            f"{_boundary_summary(reference['boundary'])}"
                        ),
                        path=run["path"],
                        run_id=run["run_id"],
                    )
                )

    workload_boundaries = [
        {
            "run_id": r["run_id"],
            "warmup": r["warmup"],
            "task_thread_count": r["threads"],
            **r["boundary"],
        }
        for r in sorted(runs, key=lambda r: r["run_id"])
        if r.get("boundary") is not None
    ]

    performance_warning_codes = {
        "insufficient_repeats",
        "excessive_cv",
        "wall_clock_outlier",
        "workload_boundary_mismatch",
    }
    performance_warnings = [
        w for w in warnings if w["code"] in performance_warning_codes
    ]
    return {
        "format_version": 1,
        "manifest_count": len(runs),
        "measured_run_count": len(measured),
        "warmup_run_count": sum(1 for r in runs if r["warmup"]),
        "errors": errors,
        "warnings": warnings,
        "groups": groups,
        "workload_boundaries": workload_boundaries,
        "valid": not errors,
        "valid_for_performance_claim": not errors and not performance_warnings,
        "thresholds": {
            "cv": cv_threshold,
            "outlier_fraction": outlier_fraction,
        },
    }


def _markdown(report: dict) -> str:
    lines = [
        "# Victoria 3 benchmark quality report",
        "",
        (
            f"Manifests: **{report['manifest_count']}**; "
            f"measured runs: **{report['measured_run_count']}**; "
            f"warm-ups: **{report['warmup_run_count']}**."
        ),
        "",
        (
            "Integrity valid: "
            f"**{'yes' if report['valid'] else 'no'}**; "
            "performance-claim ready: "
            f"**{'yes' if report['valid_for_performance_claim'] else 'no'}**."
        ),
        "",
    ]
    for title, key in (("Errors", "errors"), ("Warnings", "warnings")):
        lines += [f"## {title}", ""]
        items = report[key]
        if not items:
            lines.append("- none")
        else:
            for item in items:
                where = (
                    f" ({item.get('run_id')})"
                    if item.get("run_id")
                    else ""
                )
                lines.append(
                    f"- `{item['code']}`{where}: {item['message']}"
                )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--matrix", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--markdown", dest="markdown_path", type=Path)
    parser.add_argument("--cv-threshold", type=float, default=0.03)
    parser.add_argument("--outlier-fraction", type=float, default=0.10)
    parser.add_argument("--require-performance-ready", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = check(
            args.path,
            matrix_path=args.matrix,
            cv_threshold=args.cv_threshold,
            outlier_fraction=args.outlier_fraction,
        )
    except (Error, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.markdown_path:
        args.markdown_path.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_path.write_text(_markdown(report), encoding="utf-8")
    if not args.json_path and not args.markdown_path:
        sys.stdout.write(_markdown(report))

    if not report["valid"]:
        return 2
    if (
        args.require_performance_ready
        and not report["valid_for_performance_claim"]
    ):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
