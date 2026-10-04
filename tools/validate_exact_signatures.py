#!/usr/bin/env python3
"""Validate exact-build signature manifests against a local Victoria 3 binary."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from analyze_vic3 import Error, PE, read_input


def parse_hex_pattern(value: str) -> bytes:
    try:
        data = bytes.fromhex(value)
    except ValueError as exc:
        raise Error(f"invalid pattern_hex: {value!r}") from exc
    if not data:
        raise Error("empty byte pattern")
    return data


def section_by_name(pe: PE, name: str) -> dict:
    for section in pe.sections:
        if section["name"] == name:
            return section
    raise Error(f"PE section not found: {name}")


def count_occurrences(data: bytes, needle: bytes) -> int:
    count = 0
    offset = 0
    while True:
        offset = data.find(needle, offset)
        if offset < 0:
            return count
        count += 1
        offset += 1


def validate(binary: bytes, manifest: dict) -> dict:
    actual_hash = hashlib.sha256(binary).hexdigest()
    expected_hash = manifest.get("build", {}).get("victoria3_exe_sha256")
    if not expected_hash:
        raise Error("manifest has no build.victoria3_exe_sha256")

    pe = PE(binary)
    text = section_by_name(pe, ".text")
    text_bytes = binary[text["raw_pointer"] : text["raw_pointer"] + text["raw_size"]]
    text_rva = text["virtual_address"]

    targets = []
    all_ok = actual_hash.lower() == expected_hash.lower()
    for item in manifest.get("targets", []):
        name = item.get("name")
        signature_rva = int(str(item["signature_rva"]), 0)
        pattern = parse_hex_pattern(item["pattern_hex"])
        expected_matches = int(item.get("match_count_in_text", 1))

        relative = signature_rva - text_rva
        at_expected_rva = (
            0 <= relative <= len(text_bytes) - len(pattern)
            and text_bytes[relative : relative + len(pattern)] == pattern
        )
        actual_matches = count_occurrences(text_bytes, pattern)
        unique_as_expected = actual_matches == expected_matches
        ok = at_expected_rva and unique_as_expected
        all_ok = all_ok and ok
        targets.append(
            {
                "name": name,
                "signature_rva": f"0x{signature_rva:x}",
                "pattern_length": len(pattern),
                "expected_match_count": expected_matches,
                "actual_match_count": actual_matches,
                "matches_at_expected_rva": at_expected_rva,
                "ok": ok,
            }
        )

    return {
        "format_version": 1,
        "expected_executable_sha256": expected_hash,
        "actual_executable_sha256": actual_hash,
        "hash_ok": actual_hash.lower() == expected_hash.lower(),
        "all_targets_ok": all_ok,
        "target_count": len(targets),
        "targets": targets,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--target", default="victoria3.exe")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        binary, _ = read_input(args.input, args.target)
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = validate(binary, manifest)
    except (Error, OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    return 0 if result["all_targets_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
