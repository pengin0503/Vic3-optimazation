#!/usr/bin/env python3
"""Offline exact-build locator check for the B0 lookup contract.

Verifies an owned copy of victoria3.exe (file, ZIP or directory accepted by
analyze_vic3.read_input) against the manifest derived from the fixed
native-shadow evidence: SHA-256, PE32+/.text bounds with checked arithmetic,
a unique entry signature at the manifest RVA, and for each of the six caller
witnesses a unique signature at its call RVA, a 5-byte E8 call whose signed
rel32 reaches the entry, and return = call + 5.

Success means only that these static witnesses match. It grants no live
memory access and says nothing about relocation, unwind, ABI or runtime
return addresses. caller_entry_rva is carried from the evidence's unwind
metadata and is not re-verified here. There is deliberately no option to
substitute a manifest or an executable hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_vic3  # noqa: E402
import render_lookup_contract_manifest as manifest_tool  # noqa: E402

UINT32_MAX = (1 << 32) - 1
AMD64 = 0x8664
PE32_PLUS = 0x20B
SECTION_HEADER_SIZE = 40


def _check_uint32(value: int, what: str) -> int:
    if not 0 <= value <= UINT32_MAX:
        raise ValueError(f"{what} overflows uint32")
    return value


def _read(image: bytes, offset: int, size: int, what: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(image):
        raise ValueError(f"truncated PE: {what} is outside the input")
    return image[offset:offset + size]


def _u16(image: bytes, offset: int, what: str) -> int:
    return struct.unpack("<H", _read(image, offset, 2, what))[0]


def _u32(image: bytes, offset: int, what: str) -> int:
    return struct.unpack("<I", _read(image, offset, 4, what))[0]


def _text_section(image: bytes) -> dict:
    """Bounds-check headers and the section table, then return the .text section."""
    if _read(image, 0, 2, "DOS header") != b"MZ":
        raise ValueError("not an MZ executable")
    pe = _u32(image, 0x3C, "e_lfanew")
    if _read(image, pe, 4, "PE signature") != b"PE\0\0":
        raise ValueError("PE signature not found")
    coff = pe + 4
    machine = _u16(image, coff, "COFF machine")
    section_count = _u16(image, coff + 2, "COFF section count")
    optional_size = _u16(image, coff + 16, "COFF optional header size")
    optional = coff + 20
    if machine != AMD64:
        raise ValueError(f"expected AMD64 machine, got 0x{machine:04x}")
    if _u16(image, optional, "optional header magic") != PE32_PLUS:
        raise ValueError("expected PE32+ optional header")
    _read(image, optional, optional_size, "optional header")
    size_headers = _u32(image, optional + 60, "SizeOfHeaders")
    table = optional + optional_size
    _read(image, table, section_count * SECTION_HEADER_SIZE, "section table")
    if size_headers > len(image):
        raise ValueError("truncated PE: SizeOfHeaders is outside the input")
    # Cross-check against the repository's existing parser on the now
    # bounds-checked headers; any parser exception is a validation failure.
    try:
        parsed = analyze_vic3.PE(image)
    except (analyze_vic3.Error, struct.error, IndexError) as exc:
        raise ValueError(f"PE parse failed: {exc}") from exc
    texts = [s for s in parsed.sections if s["name"] == ".text"]
    if len(texts) != 1:
        raise ValueError(f"expected one .text section, found {len(texts)}")
    text = texts[0]
    va, vsize = text["virtual_address"], text["virtual_size"]
    raw, raw_size = text["raw_pointer"], text["raw_size"]
    _check_uint32(va + vsize, ".text virtual range")
    if va + vsize == 0 or vsize == 0:
        raise ValueError(".text virtual range is empty")
    _check_uint32(raw + raw_size, ".text raw range")
    if raw + raw_size > len(image):
        raise ValueError("truncated PE: .text raw range is outside the input")
    return {"virtual_address": va, "virtual_size": vsize, "raw_pointer": raw, "raw_size": raw_size}


def _matches(haystack: bytes, needle: bytes) -> list[int]:
    hits, start = [], 0
    while True:
        at = haystack.find(needle, start)
        if at < 0:
            return hits
        hits.append(at)
        start = at + 1


def _pattern(value: str) -> bytes:
    return bytes(int(t, 16) for t in value.split(" "))


def verify_owned_image(image: bytes, manifest: dict) -> dict:
    """Verify owned executable bytes against a manifest or raise ValueError."""
    image = bytes(image)
    if hashlib.sha256(image).hexdigest() != manifest["executable_sha256"]:
        raise ValueError("executable sha256 does not match the manifest")
    text = _text_section(image)
    if text != manifest["text_section"]:
        raise ValueError(f".text section {text} does not match the manifest {manifest['text_section']}")
    va = text["virtual_address"]
    backed = min(text["virtual_size"], text["raw_size"])  # zero-fill is not file-backed
    code = image[text["raw_pointer"]:text["raw_pointer"] + backed]

    def offset_of(rva: int, size: int, what: str) -> int:
        _check_uint32(rva + size, what)
        if not va <= rva or rva + size > va + text["virtual_size"]:
            raise ValueError(f"{what} is outside .text")
        if rva + size > va + backed:
            raise ValueError(f"{what} is not file-backed .text")
        return rva - va

    def unique_at(pattern: bytes, rva: int, what: str) -> int:
        at = offset_of(rva, len(pattern), what)
        hits = _matches(code, pattern)
        if len(hits) != 1 or hits[0] != at:
            raise ValueError(f"{what} signature matched {len(hits)} times in .text "
                             f"(required once at 0x{rva:x})")
        return len(hits)

    entry_rva = manifest["entry_rva"]
    entry_count = unique_at(_pattern(manifest["entry_pattern_hex"]), entry_rva, "entry")
    callers = []
    for c in manifest["callers"]:
        what = f"caller {c['caller_id']}"
        site = c["call_rva"]
        if c["return_rva"] != site + 5:
            raise ValueError(f"{what}: return_rva is not call_rva + 5")
        offset_of(site, 5, f"{what} call")
        pattern = _pattern(c["pattern_hex"])
        count = unique_at(pattern, site, what)
        at = site - va
        if code[at] != 0xE8:
            raise ValueError(f"{what}: not an E8 call")
        destination = site + 5 + struct.unpack("<i", code[at + 1:at + 5])[0]
        if destination != entry_rva:
            raise ValueError(f"{what}: call destination 0x{destination:x} is not the entry 0x{entry_rva:x}")
        callers.append({
            "caller_id": c["caller_id"], "call_rva": site, "return_rva": c["return_rva"],
            "caller_entry_rva": c["caller_entry_rva"], "allowed": c["allowed"],
            "call_destination_rva": destination, "pattern_match_count": count,
        })
    return {
        "schema_version": manifest["schema_version"],
        "manifest_source_sha256": manifest["manifest_source_sha256"],
        "executable_sha256": manifest["executable_sha256"],
        "entry_rva": entry_rva,
        "entry_match_count": entry_count,
        "callers": callers,
        "caller_entry_rva_verified": False,
        "static_only": True,
    }


def verify_exact_input(input_path: Path) -> dict:
    """Verify a file/ZIP/directory input against the fixed production manifest."""
    manifest = manifest_tool.load_manifest()
    try:
        image, logical = analyze_vic3.read_input(input_path, "victoria3.exe")
    except (analyze_vic3.Error, zipfile.BadZipFile) as exc:
        raise ValueError(str(exc)) from exc
    result = verify_owned_image(image, manifest)
    result["input_member"] = Path(logical).name
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", type=Path, help="victoria3.exe, a ZIP containing it, or a game directory")
    p.add_argument("--output", type=Path, required=True, help="JSON result, written only on success")
    a = p.parse_args(argv)
    try:
        if a.input.resolve() == a.output.resolve():
            raise ValueError("input and output are the same path")
        result = verify_exact_input(a.input)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    try:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"static locator witnesses match: entry 0x{result['entry_rva']:x}, "
          f"{sum(c['allowed'] for c in result['callers'])} allowed / "
          f"{sum(not c['allowed'] for c in result['callers'])} excluded callers (static only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
