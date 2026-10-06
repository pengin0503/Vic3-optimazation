#!/usr/bin/env python3
"""JSON round-trip and CLI boundary checks for lookup_reuse_runner.

Usage: VerifyRunner.py <runner-executable> [--expected <results.json>]

Standard library only. It never computes expected lookup results; it checks
the runner's JSON schema, repeatability, CLI rejection paths and (optionally)
that a fresh fixed-seed run equals the committed results file.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

SEED = 20261007
REBUILDS = 1000

REQUIRED_COUNTS = (
    "boundary_fixture_count",
    "fixture_count",
    "query_count",
    "core_hits",
    "reference_calls",
    "membership_mismatches",
    "slot_mismatches",
)
REQUIRED_OBSERVER = (
    "observed_calls",
    "candidate_attempts",
    "candidate_hits",
    "equal",
    "mismatch",
    "fallback_or_no_positive",
    "reentrant_bypass",
    "dropped_records",
    "skipped_by_reason",
)
SKIP_REASONS = ("Off", "MissingView", "MissingScope", "Reentrant", "SessionDisabled")


class Failure(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Failure(message)


def run(runner, *args):
    return subprocess.run(
        [runner, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300
    )


def run_to_file(runner, directory, name, seed=SEED, rebuilds=REBUILDS):
    path = os.path.join(directory, name)
    result = run(runner, "--seed", str(seed), "--rebuilds", str(rebuilds), "--output", path)
    check(result.returncode == 0, f"runner exited {result.returncode}: {result.stderr!r}")
    with open(path, "rb") as handle:
        raw = handle.read()
    check(b"\r" not in raw, "output contains CR characters")
    return raw, json.loads(raw.decode("utf-8"))


def check_schema(data, seed, rebuilds):
    check(data.get("schema_version") == 1, "schema_version != 1")
    check(data.get("scope") == "offline-synthetic", "scope != offline-synthetic")
    check(data.get("config") == {"seed": seed, "rebuilds": rebuilds}, "config mismatch")
    counts = data.get("counts", {})
    observer = data.get("observer", {})
    for key in REQUIRED_COUNTS:
        check(isinstance(counts.get(key), int), f"missing count {key}")
    for key in REQUIRED_OBSERVER:
        check(key in observer, f"missing observer field {key}")
    skipped = observer["skipped_by_reason"]
    for reason in SKIP_REASONS:
        check(isinstance(skipped.get(reason), int), f"missing skip reason {reason}")
    check(counts["membership_mismatches"] == 0, "membership mismatches")
    check(counts["slot_mismatches"] == 0, "slot mismatches")
    check(observer["mismatch"] == 0, "observer mismatch")
    check(observer["dropped_records"] == 0, "dropped records")
    check(counts["core_hits"] > 0, "no core hits")
    check(
        counts["core_hits"] + counts["reference_calls"] == counts["query_count"],
        "core_hits + reference_calls != query_count",
    )
    check(observer["observed_calls"] == counts["query_count"], "observed_calls != query_count")
    check(data.get("passed") is True, "passed is not true")
    check(isinstance(data.get("limits"), list) and data["limits"], "missing limits")


def check_cli_rejections(runner, directory):
    missing_dir = os.path.join(directory, "does-not-exist", "out.json")
    cases = [
        ("negative seed", ["--seed", "-1", "--rebuilds", "1"]),
        ("seed overflow", ["--seed", "4294967296", "--rebuilds", "1"]),
        ("signed seed", ["--seed", "+1", "--rebuilds", "1"]),
        ("non-decimal seed", ["--seed", "0x10", "--rebuilds", "1"]),
        ("empty seed", ["--seed", "", "--rebuilds", "1"]),
        ("zero rebuilds", ["--seed", "1", "--rebuilds", "0"]),
        ("rebuilds overflow", ["--seed", "1", "--rebuilds", "99999999999999999999999"]),
        ("missing value", ["--seed", "1", "--rebuilds"]),
        ("missing rebuilds", ["--seed", "1"]),
        ("duplicate seed", ["--seed", "1", "--seed", "2", "--rebuilds", "1"]),
        ("unknown option", ["--seed", "1", "--rebuilds", "1", "--bogus"]),
        ("unwritable output", ["--seed", "1", "--rebuilds", "1", "--output", missing_dir]),
    ]
    if os.path.exists("/dev/full"):
        # Open succeeds but the write fails (Linux).
        cases.append(("write failure", ["--seed", "1", "--rebuilds", "1", "--output", "/dev/full"]))
    for name, args in cases:
        result = run(runner, *args)
        check(result.returncode != 0, f"CLI accepted {name}: {args}")
    check(not os.path.exists(missing_dir), "unwritable output path was created")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runner")
    parser.add_argument("--expected")
    args = parser.parse_args()
    runner = os.path.abspath(args.runner)

    with tempfile.TemporaryDirectory() as directory:
        raw_a, data_a = run_to_file(runner, directory, "a.json")
        raw_b, data_b = run_to_file(runner, directory, "b.json")
        check_schema(data_a, SEED, REBUILDS)
        check(raw_a == raw_b, "two fixed-seed runs differ")

        stdout_run = run(runner, "--seed", str(SEED), "--rebuilds", str(REBUILDS))
        check(stdout_run.returncode == 0, "stdout run failed")
        check(json.loads(stdout_run.stdout.decode("utf-8")) == data_a, "stdout JSON differs")

        _, other = run_to_file(runner, directory, "other.json", seed=7, rebuilds=50)
        check_schema(other, 7, 50)

        check_cli_rejections(runner, directory)

    if args.expected:
        with open(args.expected, "rb") as handle:
            expected = json.loads(handle.read().decode("utf-8"))
        check(expected == data_a, f"fresh run differs from {args.expected}")

    print("VerifyRunner: all checks passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as failure:
        print(f"VerifyRunner: FAIL: {failure}", file=sys.stderr)
        sys.exit(1)
