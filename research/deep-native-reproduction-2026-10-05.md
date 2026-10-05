# Deep native evidence: reproduction and integrity

Target: Windows 1.14.5, exe SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`. Original archive SHA-256 `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`, 124,462,636 bytes. Base repository commit `2bde7dc4ce3f72af692f3cd625dbf839c5ef0795`. Python 3.13 and Capstone 5.0.7 were used; dependencies are declared in `tools/requirements-callgraph.txt`.

These are research recipes built on the existing PE/unwind/Capstone tools. They read the executable in memory, require its exact hash, and write selected analysis outputs. They are not native patches, runtime hooks or a general-purpose profiler. Use a separate generated output directory; do not set it to installed game/MOD/save paths or the preserved evidence directory. `finalize_deep_native_economics.py` verifies existing generated files before replacing their findings/index.

## Economics selected groups

Run from repository root with Python and Capstone installed. Use a local archive with the exact executable. PowerShell example:

```powershell
$evidenceArchive = 'E:/Vic3_data.zip'
$evidenceOutput = 'work/deep-native-reproduced/economics'
$evidenceSelections = Get-Content research/generated/deep-native-2026-10-05/economics/selections.json -Raw | ConvertFrom-Json
foreach ($selection in $evidenceSelections.PSObject.Properties) {
    $recipeArgs = @('research/recipes/inspect_deep_native_groups.py', '--archive', $evidenceArchive, '--output', $evidenceOutput, '--name', $selection.Name)
    foreach ($rva in $selection.Value) { $recipeArgs += @('--rva', $rva) }
    python @recipeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Selected decode failed' }
}
python research/recipes/finalize_deep_native_economics.py --archive $evidenceArchive --output $evidenceOutput
if ($LASTEXITCODE -ne 0) { throw 'Evidence verification failed' }
```

Five sets preserve selected instruction listings, direct/indirect edges, range hashes, RTTI references and backward branches. Compare `selected_groups` and `excluded` structurally against the committed JSON. Archive path/member formatting and JSON whitespace may differ across platforms; the exact instruction/range content must match. The original first-pass JSON predates the explicit `excluded` field; absence is an empty list. Two RVAs are excluded because there is no resolved unwind metadata. Partial decode stops inspection; no arbitrary guessed function extent is substituted.

The finalizer independently compares saved instruction bytes with input ranges and recomputes relative E8/E9 targets. The preserved data has 35 unique groups, 20,495 decoded bytes and 341 verified E8/E9 edges. It does not establish runtime reachability or performance benefit. Backward branches include epilogue/external branches and must not be counted as executed loops.

## Scheduler classification

```powershell
$schedulerOutput = 'work/deep-native-reproduced/scheduler'
python research/recipes/scan_deep_scheduler.py --archive $evidenceArchive --output $schedulerOutput
if ($LASTEXITCODE -ne 0) { throw 'Scheduler scan failed' }
python research/recipes/classify_deep_scheduler.py --archive $evidenceArchive --output $schedulerOutput
if ($LASTEXITCODE -ne 0) { throw 'Scheduler classification failed' }
```

The scan produces the large `scheduler-synchronization-evidence.json`; its generated SHA-256 is stored in `scheduler/probe-summary.json`. The full graph/inventory is reproducible but not committed. The saved focused `scheduler-classified-evidence.json` includes seven fully decoded regions, instruction windows, strings and four direct-call path witnesses. With the recorded dependency version on Windows, this JSON and `probe-summary.json` reproduced byte-identically. The summary uses platform text newlines; use structural JSON comparison on another platform. Scan coverage is limited to normal-import RIP-relative FF15/FF25 sites confirmed at unwind decode boundaries; dynamic imports, other calling forms and unresolved groups are excluded. The mixed candidate graph expands direct calls/tail-jumps, code-address references and referenced-vtable slots, reaches its 200-group budget and contains three partial groups. Address/vtable candidates are not demonstrated dynamic call targets or runtime reachability.

## Preserved artifact integrity and verification record

[artifact-index.json](generated/deep-native-2026-10-05/artifact-index.json) records hashes for saved generated artifacts, source reports and recipes. It excludes itself. Generated `.json`/`.txt` use scoped `-text` attributes and `exact_bytes` hashes; reports/recipes use explicitly marked `utf8_lf` hashes with CRLF normalized to LF, so Windows Git checkout does not change their logical hash. Do not regenerate preserved artifacts just to make their hash tests pass. [verification.json](generated/deep-native-2026-10-05/verification.json) records the completed selected-group and scheduler reproduction against the exact archive. Runtime validation remains false.

The public sources were read on 2026-10-05; their URLs, dates, applicability and verification constraints are in [sources.json](generated/deep-native-2026-10-05/public/sources.json). Historical architecture is not current binary proof. Website availability and profiling tool versions can change.

Repository unit tests are `python -m unittest discover -s tests -v`; set `VIC3_DATA` to the archive path to include the exact-build integration test. In this Windows checkout the existing native-profiler golden JSON initially had Git CRLF conversion, causing its stored byte hash check to fail. Restoring that file's committed bytes without regenerating the fixture resolved the checkout issue; it is unrelated to these research findings. The new scoped attributes preserve the new evidence hashes.
