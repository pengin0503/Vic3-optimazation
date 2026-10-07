# ModifierNode exact-build static follow-up

Date: 2026-10-05  
Target: Victoria 3 Windows 1.14.5  
Executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Scope and seed provenance

This pass is read-only static evidence. The seed is not a hand-entered function RVA: the recipe resolves the exact RTTI class `CTickTask_RecalculateModifierNodes`, requires one validated vtable candidate, and then takes its project-defined `task_specific_tail_vfunc` anchor. For 1.14.5 this resolves to:

- TypeDescriptor: `0x548be90`
- Complete Object Locator: `0x49a1f00`
- vtable: `0x44d8f58`
- task-specific tail virtual: `0x7da740`

The source-level method name of `0x7da740` is not proven by RTTI alone.

## Bounded graph result

`tools/map_hotspot_calls.build_graph` is bounded to depth 2, at most 80 function groups, and at most 65,536 bytes per group. The exact-build result contains 31 decoded groups with 12,177 decoded bytes. The seed group itself is fully decoded at `0x7da740–0x7da8de` (414 bytes).

The seed has six decoded direct calls and one tail-jump candidate:

- direct calls: `0x7d4dc0`, `0x7d60a0`, `0x420f5c0`, `0x3c014f0`, `0x421f980`, `0x42447ac`
- tail-jump candidate: `0x1014640`

`0x421f980` has no resolved unwind metadata and therefore remains unexpanded. Across the bounded traversal, 76 targets remain unexpanded: 23 because no unwind metadata was resolved and 53 because they fall beyond the depth-2 budget.

Two graph groups are preserved as partial-decode evidence rather than promoted to selected regions:

- `0x3c014f0`: 569 / 572 bytes decoded
- `0x4209900`: 1,453 / 1,484 bytes decoded

The exact-build recipe fails closed if a region chosen for the `selected_regions` set is partial. The committed selected set therefore contains the fully decoded RTTI seed region; partial graph nodes remain explicit unresolved records.

## Edge classes and shared helpers

The generated JSON preserves these evidence classes separately:

- decoded direct calls and tail-jump candidates;
- indirect call/jump sites;
- code-address materialization;
- validated RTTI/vtable references.

No bounded depth-2 edge or decoded node reaches the existing `0x7db150` scheduler-heuristic candidate, `0x7dbaa0` range-runner candidate, or `0x7dc160` dispatcher candidate. This only means that those addresses are not observed in this bounded static graph. It does **not** establish that ModifierNode work cannot reach shared scheduling code at runtime or through unresolved/indirect paths.

A raw E8 rel32 scan for the RTTI-resolved seed found no direct-call candidate to `0x7da740` in file-backed executable sections. That is not evidence against indirect/vtable invocation, tail transfers, or runtime reachability.

## What this does and does not establish

Paradox's public performance description says that Victoria 3 modifier nodes use dependency/dirty-propagation concepts and historically benefited from dependency-respecting batching and parallel work. That source supports the subsystem interpretation, but it does not prove field identities, dirty-node offsets, current 1.14.5 execution order, runtime reachability, critical-path cost, wait causality, or optimization benefit.

No offset in this pass is assigned a guessed C++ field name. No hook, detour, scheduler override, lock change, cadence change, or game-state write is produced.

## Reproduction

```text
python -m pip install -r tools/requirements-callgraph.txt
python research/recipes/reproduce_modifier_node_evidence.py \
  input-data/Vic3_data.zip \
  research/generated/modifier-node-followup-2026-10-05
```

Generated artifacts:

- `research/generated/modifier-node-followup-2026-10-05/modifier-node-callgraph.json`
- `research/generated/modifier-node-followup-2026-10-05/modifier-node-selected-regions.json`
- `research/generated/modifier-node-followup-2026-10-05/artifact-index.json`

`artifact-index.json` records the executable hash, input-container hash, canonical RTTI hash, and SHA-256 of the two derived evidence files. Re-running against the same exact input is intended to be byte-identical.
