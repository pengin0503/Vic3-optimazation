#!/usr/bin/env python3
"""Render the exact-build native profiler target database as C++ constants.

The JSON database under research/ is the only maintained copy. This tool
validates it fail-closed and emits src/native/generated/targets_1_14_5.inc
deterministically; --check verifies the committed include is current.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import native_profiler_format as fmt  # noqa: E402

DEFAULT_INPUT = Path("research/native-profiler-runtime-targets-1.14.5.json")
DEFAULT_OUTPUT = Path("src/native/generated/targets_1_14_5.inc")
SUPPORTED_SLOT_INDEX = 6
SUPPORTED_PROTOTYPE = "void(void* task_object, void* execution_context)"
SUPPORTED_KIND = "ticktask_tail_anchor"
PINNED_TARGETS = ("HandleAutonomousInvestment", "ProcessEconomicMigration", "UpdateEmployment")
_HEX = re.compile(r"0x[0-9a-fA-F]{1,8}")
_BYTE = re.compile(r"[0-9a-fA-F]{2}")


def _rva(value, what: str) -> int:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ValueError(f"invalid hex {what}: {value!r}")
    return int(value, 16)


def _uint(value, what: str, *, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value < 1 << 32:
        raise ValueError(f"invalid {what}: {value!r}")
    return value


def _text(value, what: str) -> str:
    if not isinstance(value, str) or not value.strip() or not value.isascii():
        raise ValueError(f"invalid {what}: {value!r}")
    return value


def validate_database(raw: dict) -> dict:
    """Return a normalized copy of the database or raise ValueError."""
    if not isinstance(raw, dict) or raw.get("format_version") != 1:
        raise ValueError("unsupported format_version")
    if raw.get("game_version") != "1.14.5":
        raise ValueError("unsupported game_version")
    if raw.get("executable_sha256") != fmt.EXPECTED_SHA256:
        raise ValueError("unsupported executable_sha256")
    policy = raw.get("signature_policy")
    if not isinstance(policy, dict) or policy.get("expected_match_count") != 1:
        raise ValueError("signature_policy expected_match_count must be 1")
    min_len = _uint(policy.get("minimum_length_bytes"), "minimum_length_bytes", minimum=1)
    abi = raw.get("dispatcher_abi")
    if not isinstance(abi, dict) or abi.get("vtable_slot_index") != SUPPORTED_SLOT_INDEX:
        raise ValueError("unsupported dispatcher vtable_slot_index")
    if abi.get("prototype") != SUPPORTED_PROTOTYPE or abi.get("return_value_used_by_caller") is not False:
        raise ValueError("unsupported dispatcher prototype")
    targets = raw.get("targets")
    if not isinstance(targets, list):
        raise ValueError("targets must be a list")
    if tuple(t.get("runtime_task") if isinstance(t, dict) else None for t in targets) != PINNED_TARGETS:
        raise ValueError("targets must be exactly the three pinned TickTask tail anchors")
    out_targets = []
    seen = set()
    for t in targets:
        name = _text(t.get("runtime_task"), "runtime_task")
        tid = _uint(t.get("target_id"), f"{name} target_id", minimum=1)
        if tid in seen:
            raise ValueError(f"duplicate target_id {tid}")
        seen.add(tid)
        if t.get("kind") != SUPPORTED_KIND:
            raise ValueError(f"{name}: unsupported kind")
        if t.get("vtable_slot_index") != SUPPORTED_SLOT_INDEX:
            raise ValueError(f"{name}: unsupported vtable_slot_index")
        if t.get("match_count_in_text") != 1:
            raise ValueError(f"{name}: match_count_in_text must be 1")
        function_rva = _rva(t.get("function_rva"), f"{name} function_rva")
        ranges = t.get("ranges")
        if not isinstance(ranges, list) or not ranges:
            raise ValueError(f"{name}: empty range list")
        pairs = []
        for r in ranges:
            if not isinstance(r, dict) or set(r) != {"begin_rva", "end_rva"}:
                raise ValueError(f"{name}: invalid range")
            try:
                begin, end = _rva(r["begin_rva"], "begin_rva"), _rva(r["end_rva"], "end_rva")
            except ValueError as exc:
                raise ValueError(f"{name}: invalid range ({exc})") from exc
            if not begin < end:
                raise ValueError(f"{name}: invalid range {r}")
            pairs.append((begin, end))
        ordered = sorted(pairs)
        if any(prev_end > nxt_begin for (_, prev_end), (nxt_begin, _) in zip(ordered, ordered[1:])):
            raise ValueError(f"{name}: overlapping range")
        if not any(b <= function_rva < e for b, e in pairs):
            raise ValueError(f"{name}: function_rva outside declared ranges")
        signature_rva = _rva(t.get("signature_rva"), f"{name} signature_rva")
        offset = _uint(t.get("offset_from_function_start"), f"{name} offset_from_function_start")
        if signature_rva - offset != function_rva:
            raise ValueError(f"{name}: offset_from_function_start does not map signature_rva to function_rva")
        pattern_hex = t.get("pattern_hex")
        tokens = pattern_hex.split() if isinstance(pattern_hex, str) else []
        if not tokens or not all(_BYTE.fullmatch(x) for x in tokens):
            raise ValueError(f"{name}: malformed pattern_hex (exact bytes only)")
        if len(tokens) < min_len:
            raise ValueError(f"{name}: pattern shorter than {min_len} bytes")
        out_targets.append({
            "target_id": tid,
            "runtime_task": name,
            "class_name": _text(t.get("class_name"), f"{name} class_name"),
            "kind": SUPPORTED_KIND,
            "function_rva": function_rva,
            "ranges": pairs,
            "range_strings": [{"begin_rva": r["begin_rva"], "end_rva": r["end_rva"]} for r in ranges],
            "vtable_rva": _rva(t.get("vtable_rva"), f"{name} vtable_rva"),
            "vtable_slot_index": SUPPORTED_SLOT_INDEX,
            "signature_rva": signature_rva,
            "offset_from_function_start": offset,
            "pattern": bytes(int(x, 16) for x in tokens),
        })
    return {
        "executable_sha256": raw["executable_sha256"],
        "signature_db_version": fmt.SIGNATURE_DB_VERSION,
        "targets": out_targets,
    }


def trace_targets(db: dict) -> list[dict]:
    """The V3PF metadata `targets` value for this database."""
    return [{"target_id": t["target_id"], "name": t["runtime_task"], "kind": t["kind"],
             "ranges": t["range_strings"]} for t in db["targets"]]


def canonical_target_bytes(db: dict) -> bytes:
    targets = trace_targets(db)
    fmt.validate_metadata({"build_ids": fmt.BUILD_IDS, "profiler_build_id": "codegen", "targets": targets})
    return fmt.canonical_target_bytes(targets)


def _bytes_init(raw: bytes) -> str:
    return ", ".join(f"0x{b:02x}" for b in raw)


def render(db: dict, source: Path = DEFAULT_INPUT) -> str:
    canonical = canonical_target_bytes(db)
    if not canonical.isascii():
        raise ValueError("canonical target JSON must be ASCII")
    table_hash = hashlib.sha256(canonical).digest()
    exe_hash = bytes.fromhex(db["executable_sha256"])
    lines = [
        "// Generated by tools/render_native_profiler_targets.py. DO NOT EDIT.",
        f"// Source: {source.as_posix()}",
        f"// Executable SHA-256: {db['executable_sha256']}",
        f"// Target-table SHA-256: {table_hash.hex()}",
        "// Raw RVAs are exact-build corroboration only; runtime location is signature + vtable validated.",
        "#pragma once",
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace vic3::generated {",
        "",
        "struct GeneratedRange {",
        "    std::uint32_t begin_rva;",
        "    std::uint32_t end_rva;",
        "};",
        "",
        "struct GeneratedTargetSpec {",
        "    std::uint32_t target_id;",
        "    const char* runtime_task;",
        "    const char* class_name;",
        "    const char* kind;",
        "    std::uint32_t function_rva;",
        "    const GeneratedRange* ranges;",
        "    std::size_t range_count;",
        "    std::uint32_t vtable_rva;",
        "    std::uint32_t vtable_slot_index;",
        "    std::uint32_t signature_rva;",
        "    std::uint32_t offset_from_function_start;",
        "    const std::uint8_t* pattern;",
        "    std::size_t pattern_size;",
        "    std::uint32_t expected_match_count;",
        "};",
        "",
        f'inline constexpr char kTargetDatabaseSource[] = "{source.as_posix()}";',
        f"inline constexpr std::uint8_t kExecutableSha256[32] = {{{_bytes_init(exe_hash)}}};",
        f"inline constexpr std::uint32_t kSignatureDbVersion = {db['signature_db_version']};",
        f"inline constexpr std::uint32_t kVtableSlotIndex = {SUPPORTED_SLOT_INDEX};",
        "",
    ]
    for t in db["targets"]:
        tid = t["target_id"]
        ranges = ", ".join(f"{{0x{b:x}, 0x{e:x}}}" for b, e in t["ranges"])
        lines += [
            f"inline constexpr GeneratedRange kTarget{tid}Ranges[] = {{{ranges}}};",
            f"inline constexpr std::uint8_t kTarget{tid}Pattern[] = {{{_bytes_init(t['pattern'])}}};",
        ]
    lines += ["", f"inline constexpr GeneratedTargetSpec kTargets[{len(db['targets'])}] = {{"]
    for t in db["targets"]:
        tid = t["target_id"]
        lines += [
            "    {",
            f"        {tid},",
            f'        "{t["runtime_task"]}",',
            f'        "{t["class_name"]}",',
            f'        "{t["kind"]}",',
            f"        0x{t['function_rva']:x},",
            f"        kTarget{tid}Ranges,",
            f"        {len(t['ranges'])},",
            f"        0x{t['vtable_rva']:x},",
            f"        {t['vtable_slot_index']},",
            f"        0x{t['signature_rva']:x},",
            f"        {t['offset_from_function_start']},",
            f"        kTarget{tid}Pattern,",
            f"        {len(t['pattern'])},",
            "        1,",
            "    },",
        ]
    lines += [
        "};",
        "",
        "// Exact UTF-8 bytes hashed into the V3PF header target_table_hash.",
        f"inline constexpr char kCanonicalTargetsJson[] = {json.dumps(canonical.decode('ascii'))};",
        f"inline constexpr std::size_t kCanonicalTargetsJsonSize = {len(canonical)};",
        f"inline constexpr std::uint8_t kTargetTableSha256[32] = {{{_bytes_init(table_hash)}}};",
        "",
        "}  // namespace vic3::generated",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--check", action="store_true", help="fail if --output differs; never writes")
    a = p.parse_args(argv)
    input_path = a.input if a.input.is_absolute() else ROOT / a.input
    output_path = a.output if a.output.is_absolute() else ROOT / a.output
    try:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        rel = input_path.resolve().relative_to(ROOT) if input_path.resolve().is_relative_to(ROOT) else input_path
        text = render(validate_database(raw), rel)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    encoded = text.encode("utf-8")
    if a.check:
        current = output_path.read_bytes() if output_path.is_file() else None
        if current != encoded:
            print(f"error: {output_path} is stale; rerun tools/render_native_profiler_targets.py", file=sys.stderr)
            return 1
        return 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
