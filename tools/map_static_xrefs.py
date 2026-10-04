#!/usr/bin/env python3
"""Map ASCII string anchors to candidate x64 code references and .pdata functions.

This is a static helper for the exact Victoria 3 executable under study. It does
not disassemble instructions. Instead it scans every possible 4-byte offset in
.text as a signed RIP-relative displacement and records values that resolve to a
requested string RVA. Candidate references are then mapped to PE .pdata runtime
function ranges.

Because arbitrary bytes can accidentally satisfy the displacement equation,
results are *candidates* until an actual disassembler validates the surrounding
instruction and control flow.
"""

from __future__ import annotations

import argparse
import bisect
import json
import struct
import sys
from pathlib import Path

from analyze_vic3 import Error, PE, read_input

DEFAULT_ANCHORS = [
    "clear_ticktask_timings",
    "dump_ticktask_timings",
    "log_ticktask_performance",
    "ticktask_timings.csv",
    "Threading.TaskThreadCount",
    "Threading.EnableTaskThreads",
    "TickTask.List",
    "TickTask.Graph",
    "Script.Profiling.Start",
    "Script.Profiling.Stop",
    "Script.Profiling.Restart",
    "Script.Profiling.Gui",
    "ScriptProfiling.Dump",
    "Tools.GuiDataProfiler",
    "PdxProfilerGuiWriteFrameCSV",
    "MaybeRunRangeExecutionParallelWithHeuristic",
    "pdx_task_scheduler.cpp",
    "pdx_graphjob.cpp",
    "pdx_task.cpp",
    "gamestatetick.cpp",
    "employment_helper.cpp",
    "employment_utils.cpp",
    "pop.cpp",
    "popmanager.cpp",
    "market.cpp",
    "world_market.cpp",
    "modifier.cpp",
    "ai_manager.cpp",
    "country_ai.cpp",
    "scripted_tests",
    "Game Date",
    "gametimer_%04d%02d%02d_%02d%02d%02d",
]


def section_by_name(pe: PE, name: str) -> dict:
    for section in pe.sections:
        if section["name"] == name:
            return section
    raise Error(f"PE section not found: {name}")


def file_offset_to_rva(pe: PE, offset: int) -> int | None:
    for section in pe.sections:
        start = section["raw_pointer"]
        end = start + section["raw_size"]
        if start <= offset < end:
            return section["virtual_address"] + (offset - start)
    if 0 <= offset < pe.size_headers:
        return offset
    return None


def runtime_functions(pe: PE, binary: bytes) -> list[tuple[int, int, int]]:
    pdata = section_by_name(pe, ".pdata")
    start = pdata["raw_pointer"]
    end = start + pdata["raw_size"]
    out: list[tuple[int, int, int]] = []
    for offset in range(start, max(start, end - 11), 12):
        begin, finish, unwind = struct.unpack_from("<III", binary, offset)
        if begin and begin < finish:
            out.append((begin, finish, unwind))
    out.sort()
    return out


def find_containing_function(
    functions: list[tuple[int, int, int]], rva: int
) -> tuple[int, int, int] | None:
    starts = [item[0] for item in functions]
    index = bisect.bisect_right(starts, rva) - 1
    if index >= 0:
        candidate = functions[index]
        if candidate[0] <= rva < candidate[1]:
            return candidate
    return None


def find_ascii_occurrences(binary: bytes, pe: PE, anchors: list[str]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for anchor in anchors:
        needle = anchor.encode("ascii", "strict")
        values: list[int] = []
        offset = 0
        while True:
            offset = binary.find(needle, offset)
            if offset < 0:
                break
            rva = file_offset_to_rva(pe, offset)
            if rva is not None:
                values.append(rva)
            offset += 1
        if values:
            result[anchor] = sorted(set(values))
    return result


def scan_rip_displacements(
    text: bytes | memoryview, text_rva: int, target_rvas: set[int]
) -> dict[int, list[int]]:
    """Return displacement-field RVAs whose signed disp32 resolves to a target.

    x64 RIP-relative operands use the address immediately after the displacement
    as the base. Scanning four alignment classes covers every possible byte
    offset while allowing struct.iter_unpack to stay efficient.
    """

    hits = {target: [] for target in target_rvas}
    view = memoryview(text)
    for alignment in range(4):
        available = len(view) - alignment
        if available < 4:
            continue
        count = available // 4
        aligned = view[alignment : alignment + count * 4]
        for index, (disp,) in enumerate(struct.iter_unpack("<i", aligned)):
            byte_offset = alignment + index * 4
            target = text_rva + byte_offset + 4 + disp
            if target in hits:
                hits[target].append(text_rva + byte_offset)
    return hits


def analyze_xrefs(binary: bytes, logical_path: str, anchors: list[str]) -> dict:
    pe = PE(binary)
    text_section = section_by_name(pe, ".text")
    raw_start = text_section["raw_pointer"]
    raw_end = raw_start + text_section["raw_size"]
    text = memoryview(binary)[raw_start:raw_end]

    occurrences = find_ascii_occurrences(binary, pe, anchors)
    labels_by_rva: dict[int, list[str]] = {}
    for label, rvas in occurrences.items():
        for rva in rvas:
            labels_by_rva.setdefault(rva, []).append(label)

    functions = runtime_functions(pe, binary)
    references = scan_rip_displacements(text, text_section["virtual_address"], set(labels_by_rva))

    items = []
    for label in anchors:
        rvas = occurrences.get(label)
        if not rvas:
            continue
        refs = []
        for target_rva in rvas:
            for displacement_rva in references.get(target_rva, []):
                function = find_containing_function(functions, displacement_rva)
                refs.append(
                    {
                        "target_rva": f"0x{target_rva:x}",
                        "displacement_rva": f"0x{displacement_rva:x}",
                        "function_start_rva": f"0x{function[0]:x}" if function else None,
                        "function_end_rva": f"0x{function[1]:x}" if function else None,
                        "unwind_rva": f"0x{function[2]:x}" if function else None,
                        "status": "candidate-until-disassembly-validated",
                    }
                )
        items.append(
            {
                "anchor": label,
                "occurrences": [f"0x{x:x}" for x in rvas],
                "candidate_references": refs,
            }
        )

    return {
        "format_version": 1,
        "logical_path": logical_path,
        "image_base": f"0x{pe.imagebase:x}",
        "text_rva": f"0x{text_section['virtual_address']:x}",
        "runtime_function_count": len(functions),
        "warning": (
            "Raw disp32 matches are candidates only. Validate each surrounding "
            "instruction in a disassembler before treating it as a code xref."
        ),
        "items": items,
    }


def read_anchor_file(path: Path) -> list[str]:
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            values.append(line)
    return values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--target", default="victoria3.exe")
    parser.add_argument("--anchor", action="append", dest="anchors")
    parser.add_argument("--anchors-file", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    anchors = list(args.anchors or [])
    if args.anchors_file:
        anchors.extend(read_anchor_file(args.anchors_file))
    if not anchors:
        anchors = list(DEFAULT_ANCHORS)
    anchors = list(dict.fromkeys(anchors))

    try:
        binary, logical = read_input(args.input, args.target)
        result = analyze_xrefs(binary, logical, anchors)
    except (Error, OSError, struct.error) as exc:
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
