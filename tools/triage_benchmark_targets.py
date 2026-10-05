#!/usr/bin/env python3
"""Join measured TickTask hotspots to statically recovered native anchors."""

from __future__ import annotations

import argparse
import json
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
        raise Error(f"{path}: expected a JSON object")
    return value


def normalize_task_name(name: str) -> str:
    name = name.strip()
    return name if name.startswith("CTickTask_") else f"CTickTask_{name}"


def rtti_index(document: dict) -> dict[str, dict]:
    items = document.get("classes")
    if items is None:
        items = document.get("tasks", [])
    return {
        str(item["name"]): item
        for item in items
        if isinstance(item, dict) and item.get("name")
    }


def choose_group(report: dict, variant: str, threads: int | None) -> dict:
    candidates = [g for g in report.get("groups", []) if g.get("variant") == variant]
    if not candidates:
        raise Error(f"no benchmark group for variant {variant!r}")
    if threads is not None:
        candidates = [g for g in candidates if g.get("task_thread_count") == threads]
        if not candidates:
            raise Error(f"no group for variant={variant!r}, threads={threads}")
    if len(candidates) != 1:
        values = sorted(g.get("task_thread_count") for g in candidates)
        raise Error(
            "multiple thread-count groups are available; specify --threads "
            f"(available: {values})"
        )
    return candidates[0]


def mapped_row(row: dict, index: dict[str, dict]) -> dict:
    runtime_name = str(row.get("task", ""))
    class_name = normalize_task_name(runtime_name)
    mapping = index.get(class_name)
    out = {
        "runtime_task": runtime_name,
        "class_name": class_name,
        "mean_total_ms": row.get("mean_total_ms"),
        "median_total_ms": row.get("median_total_ms"),
        "max_total_ms": row.get("max_total_ms"),
        "mean_calls": row.get("mean_calls"),
        "longest_lock_ms": row.get("longest_lock_ms"),
        "total_ms_cv": row.get("total_ms_cv"),
        "noisy": row.get("noisy") if row.get("total_ms_cv") is not None else None,
        "repeatability_assessed": bool(row.get("repeatability_assessed")) if row.get("total_ms_cv") is not None else False,
        "native_mapping_available": mapping is not None,
    }
    if mapping:
        out["native"] = {
            key: mapping.get(key)
            for key in (
                "type_descriptor_rva",
                "complete_object_locator_rva",
                "vtable_rva",
                "task_specific_tail_vfunc_rva",
                "tail_function_end_rva",
                "tail_function_size_bytes",
            )
            if key in mapping
        }
        if "tail_runtime_function" in mapping:
            out["native"]["tail_runtime_function"] = mapping["tail_runtime_function"]
        if "tail_function_group" in mapping:
            out["native"]["tail_function_group"] = mapping["tail_function_group"]
    return out


def triage(
    report: dict,
    rtti: dict,
    *,
    variant: str,
    threads: int | None,
    top: int,
) -> dict:
    if top < 1:
        raise Error("top must be at least 1")
    group = choose_group(report, variant, threads)
    index = rtti_index(rtti)

    cost_rows = [
        mapped_row(row, index) for row in group.get("tasks_by_cost", [])[:top]
    ]
    lock_rows = [
        mapped_row(row, index) for row in group.get("tasks_by_lock", [])[:top]
    ]

    return {
        "format_version": 1,
        "variant": group["variant"],
        "task_thread_count": group["task_thread_count"],
        "wall_clock_seconds": group.get("wall_clock_seconds"),
        "top_by_cost": cost_rows,
        "top_by_lock": lock_rows,
        "mapped_cost_count": sum(x["native_mapping_available"] for x in cost_rows),
        "mapped_lock_count": sum(x["native_mapping_available"] for x in lock_rows),
        "warning": (
            "This output joins runtime cost/lock evidence to static code anchors. "
            "It does not prove root cause or make a patch safe."
        ),
    }


def fmt(value, digits=3):
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else str(value)


def markdown(result: dict) -> str:
    lines = [
        "# TickTask native-target triage",
        "",
        f"Variant: **{result['variant']}**  ",
        f"Task threads: **{result['task_thread_count']}**",
        "",
        "> " + result["warning"],
        "",
        "## Top by cumulative cost",
        "",
        "| Task | Mean total ms | Longest lock ms | Native tail anchor | Mapping |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in result["top_by_cost"]:
        anchor = row.get("native", {}).get("task_specific_tail_vfunc_rva", "n/a")
        lines.append(
            f"| {row['runtime_task']} | {fmt(row.get('mean_total_ms'))} | "
            f"{fmt(row.get('longest_lock_ms'))} | {anchor} | "
            f"{'yes' if row['native_mapping_available'] else 'no'} |"
        )

    lines += [
        "",
        "## Top by longest lock",
        "",
        "| Task | Longest lock ms | Mean total ms | Native tail anchor | Mapping |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in result["top_by_lock"]:
        anchor = row.get("native", {}).get("task_specific_tail_vfunc_rva", "n/a")
        lines.append(
            f"| {row['runtime_task']} | {fmt(row.get('longest_lock_ms'))} | "
            f"{fmt(row.get('mean_total_ms'))} | {anchor} | "
            f"{'yes' if row['native_mapping_available'] else 'no'} |"
        )

    lines += [
        "",
        "## Interpretation",
        "",
        "- High cumulative cost identifies where time is spent, not why.",
        "- High longest_lock is a lead for WPR/WPA wait analysis, not proof of lock-contention root cause.",
        "- A mapped tail virtual is a reverse-engineering entry point; its source-level method name is not assumed.",
        "- No native patch should be selected until scaling and OS-level evidence agree with the hotspot.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark_report", type=Path)
    parser.add_argument("rtti_map", type=Path)
    parser.add_argument("--variant", default="vanilla")
    parser.add_argument("--threads", type=int)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--json", dest="json_output", type=Path)
    parser.add_argument("--markdown", dest="markdown_output", type=Path)
    args = parser.parse_args(argv)

    try:
        result = triage(
            load_json(args.benchmark_report),
            load_json(args.rtti_map),
            variant=args.variant,
            threads=args.threads,
            top=args.top,
        )
    except (Error, OSError) as exc:
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
