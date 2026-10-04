#!/usr/bin/env python3
"""Generate exact-build byte signatures for statically mapped function anchors.

These signatures are a secondary validator for an already hash-gated executable.
They are intentionally *not* claimed to be update-resilient across Victoria 3
builds. Future cross-build signatures should mask relocation-sensitive operands
only after disassembly confirms the instruction boundaries.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from analyze_vic3 import Error, PE, read_input


def section_by_name(pe: PE, name: str) -> dict:
    for section in pe.sections:
        if section["name"] == name:
            return section
    raise Error(f"PE section not found: {name}")


def rva_to_file_offset(pe: PE, rva: int) -> int:
    return pe.rva(rva)


def parse_target(value: str) -> tuple[str, int]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("target must use NAME=RVA")
    name, rva_text = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("target name must not be empty")
    try:
        rva = int(rva_text.strip(), 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid RVA: {rva_text!r}") from exc
    if rva < 0:
        raise argparse.ArgumentTypeError("RVA must be non-negative")
    return name, rva


def load_target_file(path: Path) -> list[tuple[str, int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    values = data["targets"] if isinstance(data, dict) else data
    out = []
    for item in values:
        out.append((str(item["name"]), int(str(item["rva"]), 0)))
    return out


def count_occurrences(haystack: bytes, needle: bytes) -> int:
    if not needle:
        return 0
    count = 0
    offset = 0
    while True:
        offset = haystack.find(needle, offset)
        if offset < 0:
            return count
        count += 1
        offset += 1


def choose_signature(
    text: bytes,
    function_offset: int,
    *,
    min_length: int = 12,
    max_length: int = 64,
    max_start_offset: int = 64,
) -> dict | None:
    """Find the shortest exact unique window near a mapped function start."""

    if function_offset < 0 or function_offset >= len(text):
        raise Error("function RVA is outside .text")
    max_available = len(text) - function_offset
    if max_available < min_length:
        return None

    max_start = min(max_start_offset, max_available - min_length)
    max_len = min(max_length, max_available)

    for length in range(min_length, max_len + 1):
        for start_offset in range(0, max_start + 1):
            if start_offset + length > max_available:
                break
            pattern = text[
                function_offset + start_offset : function_offset + start_offset + length
            ]
            matches = count_occurrences(text, pattern)
            if matches == 1:
                return {
                    "offset_from_function_start": start_offset,
                    "length": length,
                    "pattern_hex": pattern.hex(" "),
                    "match_count_in_text": matches,
                }
    return None


def generate(binary: bytes, logical_path: str, targets: list[tuple[str, int]]) -> dict:
    pe = PE(binary)
    text_section = section_by_name(pe, ".text")
    text_raw = text_section["raw_pointer"]
    text = binary[text_raw : text_raw + text_section["raw_size"]]
    text_rva = text_section["virtual_address"]

    items = []
    for name, rva in targets:
        relative = rva - text_rva
        signature = choose_signature(text, relative)
        item = {"name": name, "function_rva": f"0x{rva:x}"}
        if signature is None:
            item["status"] = "no-unique-window-found"
        else:
            item.update(signature)
            item["status"] = "exact-build-secondary-validator"
        items.append(item)

    return {
        "format_version": 1,
        "logical_path": logical_path,
        "executable_sha256_required": True,
        "warning": (
            "Exact byte windows are valid only as secondary validation after the "
            "executable hash matches. They are not cross-version signatures."
        ),
        "targets": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--target-executable", default="victoria3.exe")
    parser.add_argument("--target", action="append", type=parse_target, dest="targets")
    parser.add_argument("--targets-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    targets = list(args.targets or [])
    if args.targets_file:
        targets.extend(load_target_file(args.targets_file))
    if not targets:
        print("error: provide at least one --target NAME=RVA or --targets-file", file=sys.stderr)
        return 2

    try:
        binary, logical = read_input(args.input, args.target_executable)
        result = generate(binary, logical, targets)
    except (Error, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
