#!/usr/bin/env python3
"""Compare two Victoria 3 static-analysis snapshots for update migration."""

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
        raise Error(f"{path}: expected JSON object")
    return value


def executable_view(document: dict) -> dict:
    return document.get("executable", document)


def names(values, key: str | None = None) -> set[str]:
    if key is None:
        return {str(x) for x in values or []}
    return {str(x[key]) for x in values or [] if key in x}


def set_diff(before: set[str], after: set[str]) -> dict:
    return {
        "added": sorted(after - before),
        "removed": sorted(before - after),
        "unchanged_count": len(before & after),
    }


def section_map(exe: dict) -> dict[str, dict]:
    return {s["name"]: s for s in exe.get("pe", {}).get("sections", []) if "name" in s}


def import_dlls(exe: dict) -> set[str]:
    return {str(item["dll"]).lower() for item in exe.get("imports", []) if "dll" in item}


def rtti_class_map(document: dict) -> dict[str, dict]:
    return {
        item["name"]: item
        for item in document.get("classes", [])
        if isinstance(item, dict) and "name" in item
    }


def compare_rtti(before: dict | None, after: dict | None) -> dict | None:
    if not before or not after:
        return None
    a = rtti_class_map(before)
    b = rtti_class_map(after)
    common = sorted(set(a) & set(b))
    changed = []
    for name in common:
        old_tail = a[name].get("task_specific_tail_vfunc_rva")
        new_tail = b[name].get("task_specific_tail_vfunc_rva")
        old_slots = a[name].get("vtable_slots_rva", [])
        new_slots = b[name].get("vtable_slots_rva", [])
        if old_tail != new_tail or old_slots != new_slots:
            changed.append(
                {
                    "name": name,
                    "before_tail_vfunc_rva": old_tail,
                    "after_tail_vfunc_rva": new_tail,
                    "before_vtable_length": len(old_slots),
                    "after_vtable_length": len(new_slots),
                }
            )
    return {
        "classes": set_diff(set(a), set(b)),
        "changed_common_classes": changed,
        "changed_common_class_count": len(changed),
    }


def compare(
    before: dict,
    after: dict,
    before_rtti: dict | None = None,
    after_rtti: dict | None = None,
) -> dict:
    old = executable_view(before)
    new = executable_view(after)

    old_sections = section_map(old)
    new_sections = section_map(new)
    section_changes = []
    for name in sorted(set(old_sections) & set(new_sections)):
        a, b = old_sections[name], new_sections[name]
        fields = ("virtual_size", "raw_size", "characteristics")
        delta = {field: {"before": a.get(field), "after": b.get(field)}
                 for field in fields if a.get(field) != b.get(field)}
        if delta:
            section_changes.append({"name": name, "changes": delta})

    ticktasks = set_diff(
        names(old.get("ticktasks")),
        names(new.get("ticktasks")),
    )
    commands = set_diff(
        names(old.get("profiler_and_console_commands")),
        names(new.get("profiler_and_console_commands")),
    )
    sources = set_diff(
        names(old.get("source_paths")),
        names(new.get("source_paths")),
    )
    imports = set_diff(import_dlls(old), import_dlls(new))

    same_hash = old.get("sha256") == new.get("sha256")
    same_section_layout = (
        set(old_sections) == set(new_sections) and not section_changes
    )
    interface_stable = (
        not ticktasks["added"]
        and not ticktasks["removed"]
        and not commands["added"]
        and not commands["removed"]
    )

    return {
        "format_version": 1,
        "before": {
            "logical_path": old.get("logical_path"),
            "sha256": old.get("sha256"),
            "size_bytes": old.get("size_bytes"),
        },
        "after": {
            "logical_path": new.get("logical_path"),
            "sha256": new.get("sha256"),
            "size_bytes": new.get("size_bytes"),
        },
        "same_executable_hash": same_hash,
        "same_section_layout": same_section_layout,
        "static_interface_stable": interface_stable,
        "sections": {
            "names": set_diff(set(old_sections), set(new_sections)),
            "changed_common_sections": section_changes,
        },
        "import_dlls": imports,
        "ticktasks": ticktasks,
        "profiler_and_console_commands": commands,
        "source_paths": sources,
        "rtti": compare_rtti(before_rtti, after_rtti),
        "migration_decision": (
            "same-binary"
            if same_hash
            else "revalidate-all-native-targets-before-enabling-hooks"
        ),
        "warning": (
            "Stable strings/RTTI do not prove stable machine code. Any executable "
            "hash change invalidates exact-build signatures until regenerated "
            "and independently validated."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--before-rtti", type=Path)
    parser.add_argument("--after-rtti", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    try:
        result = compare(
            load_json(args.before),
            load_json(args.after),
            load_json(args.before_rtti) if args.before_rtti else None,
            load_json(args.after_rtti) if args.after_rtti else None,
        )
    except (Error, OSError) as exc:
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
