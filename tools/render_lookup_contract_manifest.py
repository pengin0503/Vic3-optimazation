#!/usr/bin/env python3
"""Derive the B0 lookup contract manifest from the native-shadow evidence.

The only maintained copy of the exact-build values is
research/generated/native-shadow-preparation-2026-10-07/static-evidence.json,
whose size and SHA-256 are pinned by artifact-index.json in the same folder.
This tool validates that source fail-closed, derives the locator manifest in
memory (check_lookup_contract_locator.py uses the same derivation) and emits
src/lookup_reuse_contract/generated/manifest_1_14_5.inc; --check verifies the
committed include is current and never writes.

The input source is fixed; there is no option to substitute a manifest or an
executable hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REL = "research/generated/native-shadow-preparation-2026-10-07/static-evidence.json"
INDEX_REL = "research/generated/native-shadow-preparation-2026-10-07/artifact-index.json"
SOURCE_PATH = ROOT / SOURCE_REL
INDEX_PATH = ROOT / INDEX_REL
DEFAULT_OUTPUT = ROOT / "src" / "lookup_reuse_contract" / "generated" / "manifest_1_14_5.inc"

SCHEMA_VERSION = 1
# The single executable this manifest may describe (Victoria 3 1.14.5).
PINNED_EXECUTABLE_SHA256 = "9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54"
ALLOWED_COUNT = 4
EXCLUDED_COUNT = 2
_HEX = re.compile(r"0x[0-9a-f]{1,8}")
_SHA = re.compile(r"[0-9a-f]{64}")
_BYTE = re.compile(r"[0-9a-f]{2}")


def _rva(value, what: str) -> int:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise ValueError(f"invalid hex {what}: {value!r}")
    return int(value, 16)


def _uint32(value, what: str) -> int:
    if type(value) is not int or not 0 <= value < 1 << 32:
        raise ValueError(f"invalid {what}: {value!r}")
    return value


def _pattern(value, what: str) -> bytes:
    tokens = value.split(" ") if isinstance(value, str) else []
    if not tokens or not all(_BYTE.fullmatch(t) for t in tokens):
        raise ValueError(f"malformed {what} pattern_hex: {value!r}")
    return bytes(int(t, 16) for t in tokens)


def load_source(source_path: Path = SOURCE_PATH, index_path: Path = INDEX_PATH) -> tuple[dict, str]:
    """Read the evidence after checking its size and SHA-256 against the index."""
    raw = source_path.read_bytes()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or index.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("artifact index: unsupported schema_version")
    entries = [f for f in index.get("files", []) if isinstance(f, dict) and f.get("path") == SOURCE_REL]
    if len(entries) != 1:
        raise ValueError(f"artifact index: expected one entry for {SOURCE_REL}, found {len(entries)}")
    sha = hashlib.sha256(raw).hexdigest()
    if entries[0].get("size_bytes") != len(raw) or entries[0].get("sha256") != sha:
        raise ValueError("artifact index: static evidence size or sha256 does not match")
    return json.loads(raw.decode("utf-8")), sha


def _caller(entry, entry_rva: int, what: str) -> dict:
    if not isinstance(entry, dict):
        raise ValueError(f"{what}: not an object")
    allowed = entry.get("future_candidate_allowlist")
    if type(allowed) is not bool:
        raise ValueError(f"{what}: future_candidate_allowlist must be a bool")
    site = _rva(entry.get("site_rva"), f"{what} site_rva")
    ret = _rva(entry.get("return_rva"), f"{what} return_rva")
    if ret != site + 5:
        raise ValueError(f"{what}: return_rva is not site_rva + 5")
    if _rva(entry.get("target_rva"), f"{what} target_rva") != entry_rva:
        raise ValueError(f"{what}: target_rva is not the lookup entry")
    call_hex = entry.get("call_bytes")
    if not isinstance(call_hex, str) or not re.fullmatch(r"(?:[0-9a-f]{2})+", call_hex):
        raise ValueError(f"{what}: malformed call_bytes")
    call = bytes.fromhex(call_hex)
    if len(call) != 5 or call[0] != 0xE8:
        raise ValueError(f"{what}: call_bytes is not a 5-byte E8 call")
    if site + 5 + struct.unpack("<i", call[1:])[0] != entry_rva:
        raise ValueError(f"{what}: call_bytes rel32 does not reach the lookup entry")
    sig = entry.get("signature")
    if not isinstance(sig, dict) or _rva(sig.get("begin_rva"), f"{what} signature begin_rva") != site:
        raise ValueError(f"{what}: signature does not begin at site_rva")
    pattern = _pattern(sig.get("pattern_hex"), what)
    if sig.get("length") != len(pattern) or sig.get("match_count_in_text") != 1 or pattern[:5] != call:
        raise ValueError(f"{what}: signature is not a unique pattern starting with call_bytes")
    meta = entry.get("caller_metadata")
    root = meta.get("root_runtime_function") if isinstance(meta, dict) else None
    if not isinstance(meta, dict) or meta.get("status") != "resolved" or not isinstance(root, dict):
        raise ValueError(f"{what}: caller metadata is not resolved")
    caller_entry = _rva(root.get("begin_rva"), f"{what} caller entry")
    ranges = meta.get("ranges")
    if not isinstance(ranges, list) or not any(
            isinstance(r, dict) and _rva(r.get("begin_rva"), "range") <= site
            and ret <= _rva(r.get("end_rva"), "range") for r in ranges):
        raise ValueError(f"{what}: call is outside the caller's metadata ranges")
    return {"call_rva": site, "return_rva": ret, "caller_entry_rva": caller_entry,
            "allowed": allowed, "pattern_hex": pattern.hex(" ")}


def derive_manifest(evidence: dict, source_sha256: str) -> dict:
    """Return the locator manifest for validated evidence or raise ValueError."""
    if not isinstance(evidence, dict) or evidence.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if not isinstance(source_sha256, str) or not _SHA.fullmatch(source_sha256):
        raise ValueError("invalid manifest source sha256")
    if evidence.get("executable_sha256") != PINNED_EXECUTABLE_SHA256:
        raise ValueError("unsupported executable_sha256")
    text = evidence.get("text_section")
    if not isinstance(text, dict) or text.get("name") != ".text":
        raise ValueError("missing .text section")
    text_section = {k: _uint32(text.get(k), f".text {k}")
                    for k in ("virtual_address", "virtual_size", "raw_pointer", "raw_size")}

    sig = evidence.get("entry_signature")
    excerpt = evidence.get("lookup_excerpt")
    if not isinstance(sig, dict) or not isinstance(excerpt, dict):
        raise ValueError("missing entry signature or lookup excerpt")
    entry_rva = _rva(sig.get("begin_rva"), "entry begin_rva")
    if entry_rva != _rva(excerpt.get("begin_rva"), "lookup excerpt begin_rva") or sig.get("offset_from_entry") != 0:
        raise ValueError("entry signature does not start at the lookup excerpt")
    entry_pattern = _pattern(sig.get("pattern_hex"), "entry")
    if sig.get("length") != len(entry_pattern) or sig.get("match_count_in_text") != 1:
        raise ValueError("entry signature is not a unique pattern of the declared length")
    excerpt_bytes = b"".join(bytes.fromhex(i.get("bytes", "")) for i in excerpt.get("instructions", [])
                             if isinstance(i, dict))
    if not excerpt_bytes.startswith(entry_pattern):
        raise ValueError("entry signature does not match the lookup excerpt bytes")

    entries = evidence.get("verified_callers")
    if not isinstance(entries, list):
        raise ValueError("verified_callers must be a list")
    callers = [_caller(e, entry_rva, f"caller[{i}]") for i, e in enumerate(entries)]
    sites = [c["call_rva"] for c in callers]
    if len(set(sites)) != len(sites):
        raise ValueError("duplicate caller site_rva")
    allowed = [c for c in callers if c["allowed"]]
    excluded = [c for c in callers if not c["allowed"]]
    if len(allowed) != ALLOWED_COUNT or len(excluded) != EXCLUDED_COUNT:
        raise ValueError(f"expected {ALLOWED_COUNT} allowed and {EXCLUDED_COUNT} excluded callers, "
                         f"found {len(allowed)} allowed and {len(excluded)} excluded")
    ordered = []
    for caller_id, c in enumerate(allowed + excluded, start=1):
        ordered.append({"caller_id": caller_id, **c})
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_source_sha256": source_sha256,
        "executable_sha256": evidence["executable_sha256"],
        "text_section": text_section,
        "entry_rva": entry_rva,
        "entry_pattern_hex": entry_pattern.hex(" "),
        "callers": ordered,
    }


def load_manifest() -> dict:
    """The production manifest, derived from the fixed source."""
    evidence, sha = load_source()
    return derive_manifest(evidence, sha)


def render_manifest(manifest: dict) -> str:
    lines = [
        "// Generated by tools/render_lookup_contract_manifest.py. DO NOT EDIT.",
        f"// Source: {SOURCE_REL}",
        f"// Executable SHA-256: {manifest['executable_sha256']}",
        "// Static exact-build caller witnesses for offline B0 classification only.",
        "// They grant no live-memory access and are not runtime return addresses.",
        "#pragma once",
        "",
        "#include <cstddef>",
        "#include <cstdint>",
        "",
        "namespace lookup_contract::generated {",
        "",
        "struct CallerWitness {",
        "    std::uint32_t caller_id;",
        "    std::uint32_t call_rva;",
        "    std::uint32_t return_rva;",
        "    std::uint32_t caller_entry_rva;",
        "    bool allowed;",
        "};",
        "",
        f"inline constexpr std::uint32_t kSchemaVersion = {manifest['schema_version']};",
        f'inline constexpr char kManifestSourceSha256[] = "{manifest["manifest_source_sha256"]}";',
        f'inline constexpr char kExecutableSha256[] = "{manifest["executable_sha256"]}";',
        f"inline constexpr std::uint32_t kEntryRva = 0x{manifest['entry_rva']:x};",
        "inline constexpr std::uint32_t kUnknownCallerId = 0;",
        "",
        f"inline constexpr CallerWitness kCallers[{len(manifest['callers'])}] = {{",
    ]
    for c in manifest["callers"]:
        lines.append(f"    {{{c['caller_id']}, 0x{c['call_rva']:x}, 0x{c['return_rva']:x}, "
                     f"0x{c['caller_entry_rva']:x}, {'true' if c['allowed'] else 'false'}}},")
    lines += ["};", "", "}  // namespace lookup_contract::generated", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--check", action="store_true", help="fail if --output differs; never writes")
    a = p.parse_args(argv)
    try:
        encoded = render_manifest(load_manifest()).encode("ascii")
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.check:
        current = a.output.read_bytes() if a.output.is_file() else None
        if current != encoded:
            print(f"error: {a.output} is stale; rerun tools/render_lookup_contract_manifest.py", file=sys.stderr)
            return 1
        return 0
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
