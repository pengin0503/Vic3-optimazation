#!/usr/bin/env python3
"""JSON, coverage and CLI boundary checks for lookup_contract_runner.

Usage: VerifyContractRunner.py <runner-executable> [--expected <results.json>]

Standard library only. It never computes expected lookup results; it checks
the runner's schema, repeatability, coverage of every caller witness and
result class, counter consistency, the fixed collector drop/drain case, CLI
rejection paths and (optionally) that a fresh fixed-seed run equals the
committed results file. The production runner cannot force a mismatch; the
Mismatch path is proven only by the unit tests' test-only fault seam.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile

SEED = 20261007
REBUILDS = 1000

NATIVE_COUNTERS = (
    "original_calls", "candidate_attempts", "candidate_hits", "equal", "mismatch",
    "no_candidate", "reentrant_calls", "exception_calls", "dropped_records",
)
SKIP_REASONS = (
    "Off", "SessionDisabled", "Reentrant", "MissingScope", "CallerExcluded", "MissingFixture",
    "ProofLost", "TailPositive", "EndSentinel", "Fallback", "InvalidPrimaryResult", "UnknownResult",
)
# A production run cannot disable its session (no forced mismatch).
UNREACHABLE_IN_PRODUCTION = ("SessionDisabled",)
RESULT_CLASSES = (
    "PrimaryPositive", "TailPositive", "EndSentinel", "Fallback", "InvalidPrimaryResult", "Unknown",
)
ALLOWED_CALLERS = (1, 2, 3, 4)
EXCLUDED_CALLERS = (5, 6)


class Failure(Exception):
    pass


def check(condition, message):
    if not condition:
        raise Failure(message)


def run(runner, *args):
    return subprocess.run([runner, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)


def run_to_file(runner, directory, name, seed=SEED, rebuilds=REBUILDS):
    path = os.path.join(directory, name)
    result = run(runner, "--seed", str(seed), "--rebuilds", str(rebuilds), "--output", path)
    check(result.returncode == 0, f"runner exited {result.returncode}: {result.stderr!r}")
    with open(path, "rb") as handle:
        raw = handle.read()
    check(b"\r" not in raw, "output contains CR characters")
    return raw, json.loads(raw.decode("utf-8"))


def is_count(value):
    return type(value) is int and value >= 0


def check_schema(data, seed, rebuilds):
    check(data.get("schema_version") == 1, "schema_version != 1")
    check(data.get("scope") == "offline-owned-fixtures", "unexpected scope")
    check(data.get("config") == {"seed": seed, "rebuilds": rebuilds}, "config mismatch")
    check(data.get("default_mode") == "Off", "default mode is not Off")
    check(data.get("all_game_gates_met") is False, "all_game_gates_met must be false")
    check(isinstance(data.get("limits"), list) and len(data["limits"]) >= 3, "missing limits")

    counts = data.get("counts", {})
    for key in ("boundary_fixture_count", "fixture_count", "query_count", "callback_invocations",
                "oracle_mismatches"):
        check(is_count(counts.get(key)), f"missing count {key}")
    check(counts["boundary_fixture_count"] >= 2, "boundary fixtures missing")
    check(counts["fixture_count"] == counts["boundary_fixture_count"] + rebuilds, "fixture_count mismatch")
    check(counts["oracle_mismatches"] == 0, "oracle mismatches")

    native = data.get("native", {})
    for key in NATIVE_COUNTERS:
        check(is_count(native.get(key)), f"missing native counter {key}")
    skipped = native.get("skipped_by_reason", {})
    check(tuple(skipped) == SKIP_REASONS, "skip reasons missing or out of order")
    classes = native.get("result_class_counts", {})
    check(tuple(classes) == RESULT_CLASSES, "result classes missing or out of order")

    # Original exactly once per call, and every normal return is accounted for.
    check(native["original_calls"] == counts["callback_invocations"], "original_calls != callback invocations")
    check(native["original_calls"] == counts["query_count"], "original_calls != query_count")
    normal = native["original_calls"] - native["exception_calls"]
    statuses = native["equal"] + native["mismatch"] + native["no_candidate"] + sum(skipped.values())
    check(statuses == normal, "statuses do not add up to normal returns")
    check(native["mismatch"] == 0, "mismatch in a production run")
    check(native["dropped_records"] == 0, "records dropped in the main run")
    check(native["equal"] > 0 and native["no_candidate"] > 0, "no comparisons")
    check(native["exception_calls"] > 0, "exception path not exercised")
    check(native["reentrant_calls"] > 0, "reentry not exercised")
    # A hit can still be discarded after the callback, never the reverse.
    check(native["candidate_hits"] >= native["equal"] + native["mismatch"], "candidate hits below comparisons")
    check(native["candidate_attempts"] >= native["candidate_hits"], "hits above attempts")

    for reason in SKIP_REASONS:
        if reason in UNREACHABLE_IN_PRODUCTION:
            check(skipped[reason] == 0, f"{reason} occurred in a production run")
        else:
            check(skipped[reason] > 0, f"skip reason {reason} not covered")
    for kind in RESULT_CLASSES:
        check(classes[kind] > 0, f"result class {kind} not covered")

    callers = data.get("callers", [])
    check([c.get("caller_id") for c in callers] == [0, 1, 2, 3, 4, 5, 6], "caller rows")
    for c in callers:
        for key in ("calls", "compared", "skipped"):
            check(is_count(c.get(key)), f"caller {c.get('caller_id')} missing {key}")
        check(c["calls"] > 0, f"caller {c['caller_id']} not covered")
        check(c["compared"] + c["skipped"] <= c["calls"], f"caller {c['caller_id']} counts")
        check(c.get("allowed") is (c["caller_id"] in ALLOWED_CALLERS), f"caller {c['caller_id']} allowed flag")
        if c["caller_id"] in ALLOWED_CALLERS:
            check(c["compared"] > 0, f"allowed caller {c['caller_id']} never compared")
        else:
            check(c["compared"] == 0, f"excluded/unknown caller {c['caller_id']} compared")
    check(sum(c["calls"] for c in callers) == normal, "caller rows do not add up to normal returns")

    collector = data.get("collector_case", {})
    check(collector == {"capacity": 256, "calls": 257, "original_calls": 257, "dropped": 1,
                        "drained": 256, "drained_after_refill": 1}, f"collector case {collector}")
    check(data.get("passed") is True, "passed is not true")


def check_cli(runner, directory):
    help_run = run(runner, "--help")
    check(help_run.returncode == 0 and b"usage" in help_run.stdout, "--help failed")
    missing_dir = os.path.join(directory, "does-not-exist", "out.json")
    ok = os.path.join(directory, "ok.json")
    cases = [
        ("negative seed", ["--seed", "-1", "--output", ok]),
        ("seed overflow", ["--seed", "4294967296", "--output", ok]),
        ("signed seed", ["--seed", "+1", "--output", ok]),
        ("non-decimal seed", ["--seed", "0x10", "--output", ok]),
        ("empty seed", ["--seed", "", "--output", ok]),
        ("zero rebuilds", ["--rebuilds", "0", "--output", ok]),
        ("rebuilds above limit", ["--rebuilds", "100001", "--output", ok]),
        ("rebuilds overflow", ["--rebuilds", "99999999999999999999999", "--output", ok]),
        ("non-numeric rebuilds", ["--rebuilds", "ten", "--output", ok]),
        ("missing value", ["--output", ok, "--seed"]),
        ("missing output value", ["--seed", "1", "--output"]),
        ("missing output", ["--seed", "1", "--rebuilds", "1"]),
        ("duplicate seed", ["--seed", "1", "--seed", "2", "--output", ok]),
        ("duplicate output", ["--output", ok, "--output", ok]),
        ("unknown option", ["--output", ok, "--bogus", "1"]),
        ("unwritable output", ["--rebuilds", "1", "--output", missing_dir]),
    ]
    if os.path.exists("/dev/full"):
        cases.append(("write failure", ["--rebuilds", "1", "--output", "/dev/full"]))
    for name, args in cases:
        result = run(runner, *args)
        check(result.returncode not in (0, 1), f"CLI accepted {name}: {args} -> {result.returncode}")
        check(not os.path.exists(ok), f"{name} wrote an output file")
    check(not os.path.exists(missing_dir), "unwritable output path was created")
    defaults = run(runner, "--rebuilds", "3", "--output", ok)
    check(defaults.returncode == 0, "default seed run failed")
    with open(ok, "rb") as handle:
        check(json.loads(handle.read().decode("utf-8"))["config"] == {"seed": SEED, "rebuilds": 3},
              "default seed not applied")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runner")
    parser.add_argument("--expected")
    args = parser.parse_args()
    runner = os.path.abspath(args.runner)

    with tempfile.TemporaryDirectory() as directory:
        raw_a, data_a = run_to_file(runner, directory, "a.json")
        raw_b, _ = run_to_file(runner, directory, "b.json")
        check_schema(data_a, SEED, REBUILDS)
        check(raw_a == raw_b, "two fixed-seed runs differ")
        _, other = run_to_file(runner, directory, "other.json", seed=7, rebuilds=50)
        check_schema(other, 7, 50)
        check(other["counts"] != data_a["counts"], "seed has no effect")
        check_cli(runner, directory)

    if args.expected:
        with open(args.expected, "rb") as handle:
            expected = json.loads(handle.read().decode("utf-8"))
        check(expected == data_a, f"fresh run differs from {args.expected}")

    print("VerifyContractRunner: all checks passed")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as failure:
        print(f"VerifyContractRunner: FAIL: {failure}", file=sys.stderr)
        sys.exit(1)
