#!/usr/bin/env python3
"""Run the complete offline Victoria 3 static-research pipeline in one pass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import analyze_vic3
import map_static_xrefs
import map_ticktask_rtti
import validate_exact_signatures


class Error(RuntimeError):
    pass


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_summary(
    static: dict,
    xrefs: dict,
    rtti: dict,
    signature_validation: dict | None,
) -> dict:
    exe = static["executable"]
    xref_with_candidates = sum(
        bool(item.get("candidate_references")) for item in xrefs.get("items", [])
    )
    return {
        "format_version": 1,
        "executable_sha256": exe.get("sha256"),
        "size_bytes": exe.get("size_bytes"),
        "ticktask_name_count": len(exe.get("ticktasks", [])),
        "source_path_count": len(exe.get("source_paths", [])),
        "profiler_command_count": len(exe.get("profiler_and_console_commands", [])),
        "rtti_mapped_ticktask_count": rtti.get("mapped_class_count"),
        "rtti_unmapped_ticktask_names": rtti.get("unmapped_ticktask_names", []),
        "unique_task_specific_tail_vfunc_count": rtti.get(
            "task_specific_tail_vfunc_unique_count"
        ),
        "xref_anchor_count": len(xrefs.get("items", [])),
        "xref_anchors_with_candidates": xref_with_candidates,
        "signature_validation": (
            {
                "hash_ok": signature_validation.get("hash_ok"),
                "all_targets_ok": signature_validation.get("all_targets_ok"),
                "target_count": signature_validation.get("target_count"),
            }
            if signature_validation is not None
            else None
        ),
    }


def run(
    input_path: Path,
    *,
    target: str,
    output_dir: Path,
    signature_manifest: Path | None,
) -> dict:
    try:
        binary, logical = analyze_vic3.read_input(input_path, target)
        static = {
            "format_version": 1,
            "executable": analyze_vic3.analyze(binary, logical),
        }
        xrefs = map_static_xrefs.analyze_xrefs(
            binary,
            logical,
            list(map_static_xrefs.DEFAULT_ANCHORS),
        )
        rtti = map_ticktask_rtti.analyze_rtti(binary, logical)
        signature_validation = None
        if signature_manifest is not None:
            manifest = json.loads(signature_manifest.read_text(encoding="utf-8"))
            signature_validation = validate_exact_signatures.validate(binary, manifest)
    except (
        analyze_vic3.Error,
        OSError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        raise Error(str(exc)) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "static-analysis.json", static)
    write_json(output_dir / "static-xrefs.json", xrefs)
    write_json(output_dir / "ticktask-rtti.json", rtti)
    if signature_validation is not None:
        write_json(
            output_dir / "signature-validation.json",
            signature_validation,
        )

    summary = build_summary(static, xrefs, rtti, signature_validation)
    write_json(output_dir / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--target", default="victoria3.exe")
    parser.add_argument("--signature-manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        summary = run(
            args.input,
            target=args.target,
            output_dir=args.output_dir,
            signature_manifest=args.signature_manifest,
        )
    except Error as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary.get("signature_validation") and not summary[
        "signature_validation"
    ]["all_targets_ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
