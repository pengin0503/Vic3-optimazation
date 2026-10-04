#!/usr/bin/env python3
"""Extract known performance-sensitive Victoria 3 define values from local data."""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

DEFAULT_KEYS = [
    "JOURNAL_ENTRY_UPDATE_ACTIVE",
    "JOURNAL_ENTRY_UPDATE_INACTIVE",
    "NON_TRADE_CENTER_STATE_TRADE_POTENTIAL_UPDATE_FREQUENCY",
    "COUNTRY_GOAL_STRATEGIC_UPDATE_COUNT",
    "COUNTRY_GOAL_ADJUSTMENT_UPDATE_COUNT",
    "MAX_CANDIDATES_TO_COMBINE_FOR_GOVERNMENT_ALTERNATIVES",
    "AUTONOMOUS_INVESTMENT_UPDATE_COUNT_DIVISOR",
    "AUTONOMOUS_TRADE_WEEKLY_TRADES_FRACTION_USED_FOR_FAILED_TRADE",
    "TRADE_CENTER_MINIMUM_GDP_MARKET_CAPITAL",
    "TRADE_CENTER_MINIMUM_GDP_NON_MARKET_CAPITAL",
    "POP_MERGE_MAX_WORKFORCE_1",
    "POP_MERGE_MAX_WORKFORCE_2",
    "POP_MERGE_MAX_WORKFORCE_3",
    "POP_MERGE_MAX_WORKFORCE_4",
    "POP_MERGE_MIN_NUM_POPS_SAME_PROFESSION_1",
    "POP_MERGE_MIN_NUM_POPS_SAME_PROFESSION_2",
    "POP_MERGE_MIN_NUM_POPS_SAME_PROFESSION_3",
    "WORKFORCE_RATIO_MAX_UNEMPLOYMENT_FACTOR_1",
    "WORKFORCE_RATIO_MAX_UNEMPLOYMENT_FACTOR_2",
    "WORKFORCE_RATIO_MAX_UNEMPLOYMENT_FACTOR_3",
    "WORKFORCE_RATIO_MAX_UNEMPLOYMENT_FACTOR_4",
    "POP_MERGE_START_POPS",
    "POP_MERGE_MAX_TARGET_POPS",
    "MAP_MARKER_FULL_UPDATE_FREQUENCY",
    "ALERTS_FRAMES_BETWEEN_UPDATES",
    "COA_FLAGS_FRAMES_BETWEEN_UPDATES",
    "POWER_BLOC_COLOR_UPDATE_NUM_FRAMES_BETWEEN",
    "REVOLUTION_MAP_OBJECT_UPDATE_PROVINCES_PER_FRAME",
    "REVOLUTION_MAP_OBJECT_UPDATE_MAX_TIME_PER_FRAME",
    "DYNAMIC_TERRAIN_LAZY_UPDATE_PROVINCES_PER_FRAME",
    "DYNAMIC_TERRAIN_LAZY_UPDATE_MAX_TIME_PER_FRAME",
    "BATTLE_CONDITION_MIN_TICKS_BETWEEN_UPDATE_DEFAULT",
]

ASSIGNMENT = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


class Error(RuntimeError):
    pass


def candidate_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    if normalized.startswith("__macosx/") or "/__macosx/" in normalized:
        return False
    if not normalized.endswith(".txt"):
        return False
    return (
        "/game/common/defines/" in f"/{normalized}"
        or "/game/common/game_rules/" in f"/{normalized}"
    )


def read_text_files(input_path: Path):
    if not input_path.exists():
        raise Error(f"input path does not exist: {input_path}")

    if input_path.is_file() and zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path) as archive:
            for name in sorted(archive.namelist(), key=str.lower):
                if not candidate_file(name):
                    continue
                try:
                    text = archive.read(name).decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = archive.read(name).decode("cp1252", "replace")
                yield name, text
        return

    if input_path.is_dir():
        files = sorted(input_path.rglob("*.txt"), key=lambda p: p.as_posix().lower())
        for path in files:
            logical = path.as_posix()
            if not candidate_file("/" + logical):
                # A user may point directly at game/. In that case test the
                # relative suffix as well.
                low = logical.lower()
                if "common/defines/" not in low and "common/game_rules/" not in low:
                    continue
            yield logical, path.read_text(encoding="utf-8-sig", errors="replace")
        return

    raise Error("input must be a Victoria 3 directory or ZIP archive")


def strip_inline_comment(value: str) -> str:
    # Clausewitz/Jomini define values in the target files do not use quoted '#'
    # in the keys we track. Keeping this parser deliberately narrow avoids
    # pretending to be a full script parser.
    return value.split("#", 1)[0].rstrip()


def extract_from_text(path: str, text: str, wanted: set[str]) -> list[dict]:
    lines = text.splitlines()
    out = []
    comment_buffer: list[str] = []
    for index, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            comment_buffer.append(stripped.lstrip("#").strip())
            comment_buffer = comment_buffer[-4:]
            continue

        match = ASSIGNMENT.match(line)
        if not match:
            if stripped:
                comment_buffer = []
            continue

        key, raw_value = match.groups()
        if key in wanted:
            out.append(
                {
                    "key": key,
                    "value": strip_inline_comment(raw_value),
                    "file": path,
                    "line": index,
                    "preceding_comments": list(comment_buffer),
                }
            )
        comment_buffer = []
    return out


def extract(input_path: Path, keys: list[str]) -> dict:
    wanted = set(keys)
    occurrences = []
    for path, text in read_text_files(input_path):
        occurrences.extend(extract_from_text(path, text, wanted))

    found = {item["key"] for item in occurrences}
    return {
        "format_version": 1,
        "requested_keys": sorted(wanted),
        "found_key_count": len(found),
        "missing_keys": sorted(wanted - found),
        "occurrences": sorted(
            occurrences,
            key=lambda item: (item["key"], item["file"].lower(), item["line"]),
        ),
        "warning": (
            "These values are performance controls or causal-test knobs, not "
            "automatic optimization recommendations. Changing cadence, search "
            "breadth, or Pop consolidation may change simulation semantics."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--key", action="append", dest="keys")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    keys = args.keys or list(DEFAULT_KEYS)
    try:
        result = extract(args.input, keys)
    except (Error, OSError, zipfile.BadZipFile) as exc:
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
