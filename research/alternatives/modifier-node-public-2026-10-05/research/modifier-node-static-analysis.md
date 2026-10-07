# ModifierNode exact-build static follow-up

Date: 2026-10-05  
Target: Victoria 3 Windows 1.14.5  
Executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Scope

This pass follows `CTickTask_RecalculateModifierNodes` using only exact-build static evidence. It does not establish runtime reachability, critical-path cost, wait causality, dirty-node field semantics, or an optimization benefit.

The target is resolved by the current MSVC RTTI map, not by a free-form RVA:

- TypeDescriptor RVA: `0x548be90`
- vtable RVA: `0x44d8f58`
- class-specific `task_specific_tail_vfunc`: `0x7da740`
- static confidence: `confirmed_static`
- runtime status: unverified

The public Paradox description of Modifier Nodes is used only as architecture context. It does not promote offsets or helper candidates in this executable to source-level dirty-propagation names.

## Bounded graph

The reproduction recipe calls the existing `map_hotspot_calls.build_graph(..., max_depth=2)` implementation with the RTTI-resolved seed. The resulting exact-build bounded graph contains 31 resolved unwind groups.

Evidence classes remain distinct in the generated JSON:

- direct calls;
- tail-jump candidates;
- indirect call/jump sites;
- code-address references;
- RTTI/vtable references.

The seed group is `0x7da740-0x7da8de` (414 bytes) and decodes completely. Its static transfers include direct calls, one separately classified tail-jump candidate, and no promotion of indirect or pointer evidence to direct calls.

Two expanded groups are only partially decoded by the pinned decoder:

- `0x3c014f0-0x3c0172c`: 569 / 572 bytes decoded;
- `0x4209900-0x4209ecc`: 1453 / 1484 bytes decoded.

They remain in the bounded graph as explicit partial evidence but are not selected as trusted decoded regions. A selected region that is partial causes the recipe to fail closed.

## Shared scheduler helpers

The known static candidates below are checked only for actual appearance in this depth-2 graph:

- dispatcher candidate `0x7dc160`;
- range-runner candidate `0x7dbaa0`;
- scheduler-heuristic candidate `0x7db150`.

None is expanded or referenced by an expanded direct/code-address edge in this bounded ModifierNode graph. Therefore this pass does not claim a static connection from `CTickTask_RecalculateModifierNodes` to those shared helpers.

The direct E8 caller scan for the RTTI-resolved seed also yields no exact-build candidate callsite. That is not evidence that the task is unreachable: virtual dispatch, indirect calls, tail transfers, or paths outside the bounded evidence remain possible.

## Generated artifacts

- `research/generated/modifier-node-followup-2026-10-05/modifier-node-callgraph.json`
- `research/generated/modifier-node-followup-2026-10-05/modifier-node-selected-regions.json`
- `research/generated/modifier-node-followup-2026-10-05/artifact-index.json`

The index records SHA-256 for every derived JSON artifact. JSON is rendered with sorted keys and stable formatting so repeated runs from the same exact input are byte-identical.

## Reproduction

```text
python -m pip install -r tools/requirements-callgraph.txt
python research/recipes/reproduce_modifier_node_evidence.py \
  input-data/Vic3_data.zip \
  research/generated/modifier-node-followup-2026-10-05
```

The recipe verifies the executable SHA-256 before creating output, resolves the TickTask through RTTI, uses the existing chained-unwind/callgraph/caller tooling, and performs no game hook, injection, state write, scheduler override, lock removal, or cadence change.
