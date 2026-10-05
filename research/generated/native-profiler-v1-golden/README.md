# Synthetic native profiler v1 golden

These are synthetic wire-format fixtures, not captured game measurements.
The executable/build IDs identify the supported metadata gate, not real execution.
8 records: threads 7 and 8, 2 function pairs, 1 scheduler decision, 1 wait pair,
and 1 counter. There are no dropped, malformed or unknown events.

Explicit regeneration (never run automatically in the golden test):

`python research/recipes/reproduce_native_profiler_golden.py`

Tests compare the committed binary to committed expected JSON. The codec tests
also pin hand-derived literal bytes for all six payload types and header offsets.
`artifact-index.json` records SHA-256 for both files.

A future C++ writer must serialize explicit little-endian fields at the documented
offsets, canonicalize targets with UTF-8/sorted keys/compact separators, zero pad,
and reproduce these bytes for identical fixture values. Parser semantics must
retain file order, pair only within a thread/family/target, skip valid extensions,
and surface data loss. C++ ring-buffer correctness, memory ordering, allocation,
writer overhead and game attach behavior have not been implemented or proven.
