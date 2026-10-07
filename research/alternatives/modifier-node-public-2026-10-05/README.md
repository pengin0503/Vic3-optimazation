# Preserved public modifier-node variant

Source: `public-architecture-static-followups-2026-10-05` at
`21d5fbe0adeb87ab913aec5b7d92e02807b58aef`.

The six files below retain their original repository-relative paths under this
folder and are byte-identical to that commit. The regular repository paths use
the work-branch variant at `f2e028b56840ae96f2fc08a741331e28cd865f4c`, which
preserves full graph fields, input-container/RTTI provenance and strict RTTI
hash validation. These are different graph schemas, not interchangeable JSON.

- `research/generated/modifier-node-followup-2026-10-05/artifact-index.json`
- `research/generated/modifier-node-followup-2026-10-05/modifier-node-callgraph.json`
- `research/generated/modifier-node-followup-2026-10-05/modifier-node-selected-regions.json`
- `research/modifier-node-static-analysis.md`
- `research/recipes/reproduce_modifier_node_evidence.py`
- `tests/test_modifier_node_static_followup.py`

For reproduction, use an isolated copy of the integrated repository and overlay
these six paths at the repository root. Then run the preserved test with
`python -m unittest discover -s tests -p test_modifier_node_static_followup.py -v`.
Set `VIC3_DATA` to the exact input ZIP to include the real-input tests.
The archived recipe/test are not active entry points of the integrated tree.
The merge commit also retains the public branch as a parent.
