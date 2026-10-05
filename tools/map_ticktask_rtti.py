#!/usr/bin/env python3
"""Recover Victoria 3 TickTask MSVC RTTI, vtables, and task-specific tail virtuals.

This is a static, dependency-free helper for x64 MSVC RTTI. It maps decorated
CTickTask_* TypeDescriptors to Complete Object Locators (COLs), then maps those
COLs to vtables. It also records the final virtual slot for each concrete
TickTask class because, in Victoria 3 1.14.5, that slot is unique per mapped
class and is therefore a high-value code-mapping anchor.

Important: uniqueness does NOT prove a source-level method name. The final slot
is reported as task_specific_tail_vfunc, not "Execute", until dynamic or deeper
semantic analysis proves its role.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from analyze_vic3 import Error, PE, read_input
from runtime_function_groups import RuntimeFunctionIndex, group_metadata

RTTI_TICKTASK = re.compile(
    rb"\.\?AV(CTickTask_[A-Za-z0-9_]+)@(?:\?A0x[0-9A-Fa-f]+@)?@\x00"
)
ANY_TICKTASK = re.compile(rb"CTickTask_[A-Za-z0-9_]+")


def section_by_name(pe: PE, name: str) -> dict:
    for section in pe.sections:
        if section["name"] == name:
            return section
    raise Error(f"PE section not found: {name}")


def file_offset_to_rva(pe: PE, offset: int) -> int | None:
    if offset < pe.size_headers:
        return offset
    for section in pe.sections:
        start = section["raw_pointer"]
        end = start + section["raw_size"]
        if start <= offset < end:
            return section["virtual_address"] + (offset - start)
    return None


def data_sections(pe: PE) -> list[dict]:
    return [s for s in pe.sections if s["name"] in (".rdata", ".data")]


def aligned_range(start: int, end: int, alignment: int):
    current = start + ((alignment - (start % alignment)) % alignment)
    return range(current, end, alignment)


def find_type_descriptors(binary: bytes, pe: PE) -> dict[int, str]:
    """Return TypeDescriptor RVA -> normalized CTickTask class name."""

    out: dict[int, str] = {}
    for match in RTTI_TICKTASK.finditer(binary):
        name_rva = file_offset_to_rva(pe, match.start())
        if name_rva is None or name_rva < 16:
            continue
        out[name_rva - 16] = match.group(1).decode("ascii")
    return out


def find_complete_object_locators(
    binary: bytes, pe: PE, type_descriptors: dict[int, str]
) -> dict[int, list[int]]:
    """Return TypeDescriptor RVA -> validated x64 MSVC COL RVAs.

    x64 MSVC Complete Object Locator:
      uint32 signature      (1)
      uint32 offset
      uint32 cdOffset
      uint32 pTypeDescriptor  (image-relative)
      uint32 pClassDescriptor (image-relative)
      uint32 pSelf            (image-relative, equals COL RVA)
    """

    wanted = set(type_descriptors)
    out: dict[int, list[int]] = collections.defaultdict(list)
    for section in data_sections(pe):
        start = section["raw_pointer"]
        end = start + section["raw_size"]
        for offset in aligned_range(start, max(start, end - 23), 4):
            signature, _, _, ptype, _, pself = struct.unpack_from("<6I", binary, offset)
            if signature != 1 or ptype not in wanted:
                continue
            col_rva = section["virtual_address"] + (offset - start)
            if pself == col_rva:
                out[ptype].append(col_rva)
    return {key: sorted(set(values)) for key, values in out.items()}


def find_vtable_locator_slots(
    binary: bytes, pe: PE, col_rvas: set[int]
) -> dict[int, list[tuple[int, int]]]:
    """Return COL RVA -> [(locator_slot_rva, vtable_rva), ...].

    On x64 MSVC, vtable[-1] is an absolute pointer to the COL and the first
    virtual function pointer starts eight bytes later.
    """

    absolute_to_col = {pe.imagebase + col: col for col in col_rvas}
    out: dict[int, list[tuple[int, int]]] = collections.defaultdict(list)
    for section in data_sections(pe):
        start = section["raw_pointer"]
        end = start + section["raw_size"]
        for offset in aligned_range(start, max(start, end - 7), 8):
            value = struct.unpack_from("<Q", binary, offset)[0]
            col = absolute_to_col.get(value)
            if col is None:
                continue
            locator_rva = section["virtual_address"] + (offset - start)
            out[col].append((locator_rva, locator_rva + 8))
    return {key: sorted(set(values)) for key, values in out.items()}


def read_vtable(
    binary: bytes, pe: PE, vtable_rva: int, *, max_slots: int = 24
) -> list[int]:
    text = section_by_name(pe, ".text")
    text_start = text["virtual_address"]
    text_end = text_start + max(text["virtual_size"], text["raw_size"])
    offset = pe.rva(vtable_rva)
    functions: list[int] = []
    for index in range(max_slots):
        value = struct.unpack_from("<Q", binary, offset + index * 8)[0]
        rva = value - pe.imagebase
        if not (text_start <= rva < text_end):
            break
        functions.append(rva)
    return functions


def runtime_functions(binary: bytes, pe: PE) -> list[tuple[int, int, int]]:
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


def runtime_function_for(
    functions: list[tuple[int, int, int]], rva: int
) -> tuple[int, int, int] | None:
    # Most vtable methods point at function starts; prefer exact match.
    for begin, finish, unwind in functions:
        if begin == rva:
            return begin, finish, unwind
    # Fall back to containing range for thunks or unusual metadata.
    lo, hi = 0, len(functions)
    while lo < hi:
        mid = (lo + hi) // 2
        if functions[mid][0] <= rva:
            lo = mid + 1
        else:
            hi = mid
    index = lo - 1
    if index >= 0:
        begin, finish, unwind = functions[index]
        if begin <= rva < finish:
            return begin, finish, unwind
    return None


def slot_frequency(classes: list[dict]) -> dict[str, list[dict]]:
    slots: dict[int, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    for item in classes:
        for index, value in enumerate(item["vtable_slots_rva"]):
            slots[index][value] += 1
    return {
        str(index): [
            {"function_rva": f"0x{rva:x}", "class_count": count}
            for rva, count in counter.most_common()
        ]
        for index, counter in sorted(slots.items())
    }


def analyze_rtti(binary: bytes, logical_path: str) -> dict:
    pe = PE(binary)
    type_descriptors = find_type_descriptors(binary, pe)
    col_by_type = find_complete_object_locators(binary, pe, type_descriptors)
    all_cols = {col for values in col_by_type.values() for col in values}
    vtable_by_col = find_vtable_locator_slots(binary, pe, all_cols)
    functions = runtime_functions(binary, pe)
    function_index = RuntimeFunctionIndex(binary, pe, functions)

    classes: list[dict] = []
    for type_rva, name in sorted(type_descriptors.items(), key=lambda item: item[1]):
        candidates: list[dict] = []
        for col_rva in col_by_type.get(type_rva, []):
            for locator_rva, vtable_rva in vtable_by_col.get(col_rva, []):
                slots = read_vtable(binary, pe, vtable_rva)
                if not slots:
                    continue
                tail = slots[-1]
                function = runtime_function_for(functions, tail)
                candidate = {
                    "complete_object_locator_rva": col_rva,
                    "vtable_locator_slot_rva": locator_rva,
                    "vtable_rva": vtable_rva,
                    "vtable_slots_rva": slots,
                    "task_specific_tail_vfunc_rva": tail,
                }
                if function:
                    begin, finish, unwind = function
                    candidate["tail_runtime_function"] = {
                        "begin_rva": begin,
                        "end_rva": finish,
                        "size_bytes": finish - begin,
                        "unwind_rva": unwind,
                    }
                    candidate["tail_function_group"] = group_metadata(function_index.group_for(tail))
                candidates.append(candidate)

        # The target 1.14.5 build maps each concrete class to exactly one vtable.
        # Keep all candidates so future builds do not silently lose information.
        if candidates:
            primary = candidates[0]
            classes.append(
                {
                    "name": name,
                    "type_descriptor_rva": type_rva,
                    "vtable_candidate_count": len(candidates),
                    **primary,
                    "additional_vtables": candidates[1:],
                }
            )

    all_names = sorted({x.decode("ascii") for x in ANY_TICKTASK.findall(binary)})
    mapped_names = {item["name"] for item in classes}
    lengths = collections.Counter(len(item["vtable_slots_rva"]) for item in classes)
    tails = collections.Counter(item["task_specific_tail_vfunc_rva"] for item in classes)

    # Convert internal integers to stable hex strings only at the JSON boundary.
    def convert(value):
        if isinstance(value, dict):
            out = {}
            for key, item in value.items():
                if key.endswith("_rva") and isinstance(item, int):
                    out[key] = f"0x{item:x}"
                elif key == "vtable_slots_rva":
                    out[key] = [f"0x{x:x}" for x in item]
                else:
                    out[key] = convert(item)
            return out
        if isinstance(value, list):
            return [convert(x) for x in value]
        return value

    converted_classes = [convert(item) for item in classes]
    return {
        "format_version": 1,
        "logical_path": logical_path,
        "executable_sha256": hashlib.sha256(binary).hexdigest(),
        "image_base": f"0x{pe.imagebase:x}",
        "all_ticktask_name_count": len(all_names),
        "rtti_type_descriptor_count": len(type_descriptors),
        "mapped_class_count": len(classes),
        "runtime_function_fragment_count": len(functions),
        "invalid_unwind_fragment_count": len(function_index.errors),
        "unmapped_ticktask_names": sorted(set(all_names) - mapped_names),
        "vtable_length_distribution": {
            str(length): count for length, count in sorted(lengths.items())
        },
        "task_specific_tail_vfunc_unique_count": len(tails),
        "task_specific_tail_vfunc_max_shared_count": max(tails.values(), default=0),
        "slot_frequency": slot_frequency(classes),
        "warning": (
            "The final virtual slot is a high-value class-specific code anchor, "
            "but its source-level method name is not proven by RTTI alone. "
            "tail_runtime_function is the containing first fragment only; "
            "tail_function_group records chained fragments without filling gaps."
        ),
        "classes": converted_classes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--target", default="victoria3.exe")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        binary, logical = read_input(args.input, args.target)
        result = analyze_rtti(binary, logical)
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
