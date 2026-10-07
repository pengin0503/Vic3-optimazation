# Offline locator hardening verification

Plan: ../plans/2026-10-08-offline-locator-hardening.md
Base: c13bb2730a38a130186e1edb389f9ed8e1f54eef

Baseline: Python 195 tests OK, 2 skips (VIC3_DATA unset).
The first materialized snapshot lacked golden index/gitattributes and git
metadata; hydrating exact pinned blobs and initializing a local inspection
repository resolved those environment-only failures before any code edits.

Pre-flight: Task 2 shares the locator but not Task 1's metadata API.
Ruling: use a SHA-verified isolated snapshot and GitHub tree/commit API,
because an authenticated local clone is unavailable; preserve the full
remote base tree and update main with a lease. No unrelated files are staged.
Ruling: approval pauses are waived by the user. Execute inline and perform
self-review without subagents, following the established project preference.
Cost: no independent fresh-context review in this turn.

Native evidence gates remain unmet. No game process is run.

Task 1 RED: 16 failed assertions and one missing-field access across 29 tests
(one optional skip). Replaced the missing-field access with an explicit
assertion before implementing. Wrong roots, gaps, overlap, invalid chains
and unbacked directories were incorrectly accepted by the old code.
Task 1 GREEN: locator 29 tests OK (one skip); complete suite with supplied
ZIP: 203 tests OK, no skips, in 13.912s.

Task 2 RED: external hard links from directory-root, binaries, and recursive
member cases were all incorrectly accepted (three failed subcases).
Task 2 Ruling: extract resolve_input_file from analyze_vic3.read_input so
selection is shared with output protection without reading the exe twice.
Cost: existing file/directory readers share this helper; full-suite regression
is required. ZIP member selection is unchanged.

Task 2 GREEN: complete Python suite with exact ZIP: 205 tests OK, no skips,
in 15.941s. GCC 13.3 Release with warnings-as-errors built successfully;
CTest 11/11 and VerifyContractRunner passed. Manifest --check passed.

Final review: self-review (subagents prohibited by project preference).
Two Important findings: a declared directory count above 16 could exceed
the optional header despite clamping, and SizeOfHeaders could end within
the section table. Both were reproduced with failed assertions (33 locator
tests, two failures, one optional skip) before the single fix pass.
No native gate is inferred from these checks.

Reference for metadata interpretation:
https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64
The existing resolver reconstructs chain association; it deliberately does
not emulate Windows unwinding or validate the stack effects of each opcode.

Final GREEN: Python 207 tests OK, no skips, with the exact ZIP (17.906s).
CTest 11/11 OK; generated manifest remains byte-current. The locator result
records all six verified roots and fragment counts 5, 4, 1, 1, 1, 1.
The generated result and SHA-256/size index are preserved under
research/generated/offline-locator-hardening-2026-10-08/ with -text attributes.

Mutation check: executing the unmodified c13bb27 locator in memory against
the current chained-root, wrong-root, and external-hard-link tests caused
five assertion failures and no errors. No production or input files were
changed for this check. This also confirmed the missing-field RED assertion
after it was corrected from a KeyError to an explicit assertion.

Review outcome after fixes: no remaining Critical or Important findings in
the changed files; no deferred Minor findings. Review is by the author only.
Unchanged: Stage A/B0 C++ implementation, generated manifest include, fixed
native-shadow evidence, native loader/DLL, targets, V3PF and golden assets.

Remaining runtime gates: loader real-game connection/code 4 cause, protected
live read window and table lifetime, worker/job scope, actual result pointers,
native ABI, relocation/unwind behavior, runtime return addresses, and observer
overhead. Their state is unchanged. No speedup claim or lookup bypass.

Implementation commit: 99ef9728b5ce0a0d7d7c331811522c331d412973.
main advanced from c13bb27 to that commit without force, PR or branch deletion.
The resulting tree differs at exactly 11 intended paths; 465 existing blobs
are unchanged.

Ruling: the connector's expected-SHA update failed twice with GitHub GraphQL
UNKNOWN errors and left main unchanged. Re-read main, use force=false without
the broken optional lease parameter, then verify the resulting head.
Cost: no atomic compare-and-swap lease; a non-fast-forward race is rejected by
the normal force=false update rather than overwriting another commit.

CI status: repeated Actions queries for head_sha=99ef972... returned zero runs.
The latest existing successful tests/B0 runs still refer to c13bb27, not this
implementation. No claim of fresh CI/MSVC/Clang success is made. The connector
exposes rerun of existing runs, but no workflow_dispatch operation for a new
head; rerunning old runs would not test this commit. No credentials, new PR,
browser session, permission change or synthetic status is used to work around
that limitation. The reason for the missing automatic trigger is unknown.

Additional CI-mode local run (VIC3_DATA unset): Python 207 OK, two expected
skips. Artifact hash/size and -text attribute checks passed. Supplied ZIP
SHA-256 remains 79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34.
