# TickTask RTTI and vtable findings — Victoria 3 1.14.5

Date: 2026-10-04

Target executable SHA-256:

`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Summary

A static MSVC x64 RTTI pass substantially improves the TickTask map without requiring a running Windows process.

The executable contains:

- **260** distinct `CTickTask_*` names in strings,
- **258** matching concrete `CTickTask_*` MSVC TypeDescriptors,
- **258** validated x64 Complete Object Locators,
- **258** mapped vtables.

The two TickTask names present in strings but not mapped to a matching concrete RTTI TypeDescriptor are:

- `CTickTask_CheckNonFulfillments`
- `CTickTask_MoveFormations`

This does not prove those tasks are absent. They may be referenced as names without a concrete emitted RTTI class in this build, may be aliases, or may be implemented through a different class shape.

## Method

The reproducible implementation is `tools/map_ticktask_rtti.py`.

For each decorated class name such as:

`.?AVCTickTask_UpdateEmployment@?A0x0778c8c9@@`

the tool:

1. identifies the MSVC `TypeDescriptor` 16 bytes before the decorated name,
2. scans `.rdata` and `.data` for x64 Complete Object Locators whose:
   - signature is 1,
   - `pTypeDescriptor` matches the TypeDescriptor RVA,
   - `pSelf` equals the candidate COL RVA,
3. scans for the absolute pointer `image_base + COL_RVA`,
4. treats the following qword as the vtable start,
5. reads consecutive virtual-function pointers while they point into `.text`,
6. maps the final virtual slot to PE `.pdata` where unwind/runtime-function metadata exists.

The tool keeps all vtable candidates instead of silently assuming there can only be one in future builds.

## Vtable shape

For the 258 mapped classes in 1.14.5:

- 189 vtables have 7 slots,
- 69 vtables have 8 slots.

Shared slots are extremely regular:

| Slot | Dominant function RVA | Classes using it |
| ---: | ---: | ---: |
| 1 | `0x3bf7200` | 258 / 258 |
| 3 | `0x3bf7270` | 258 / 258 |
| 5 | `0x62d680` | 258 / 258 |
| 2 | `0x62d680` | 252 / 258 |
| 4 | `0x1808250` | 251 / 258 |
| 6 | `0x7d76b0` | 69 / 258 |

The most important structural observation is that the **final virtual slot is unique for every one of the 258 mapped concrete TickTask classes**.

Therefore the final slot is a very strong class-specific code anchor.

It is deliberately named `task_specific_tail_vfunc` in the tooling. RTTI/vtable position alone does **not** prove that the source-level method is named `Execute`, `Run`, or any other specific name.

## High-value task mappings

| TickTask | TypeDescriptor RVA | COL RVA | Vtable RVA | Slots | Task-specific tail virtual | Runtime size when available |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `CTickTask_UpdateEmployment` | `0x556fbb8` | `0x4a930f8` | `0x4590800` | 7 | `0x13b8310` | 555 bytes |
| `CTickTask_UpdateStatePopNeedCache` | `0x556f8f0` | `0x4a92fe0` | `0x4590dd8` | 8 | `0x13b7e70` | 104 bytes |
| `CTickTask_ProcessPopPurchases` | `0x5518af0` | `0x4a3ef68` | `0x4550fd8` | 7 | `0xee74b0` | 247 bytes |
| `CTickTask_RecalculateModifierNodes` | `0x548be90` | `0x49a1f00` | `0x44d8f58` | 8 | `0x7da740` | 414 bytes |
| `CTickTask_UpdateWorldMarket` | `0x5518878` | `0x4a3efe0` | `0x4551108` | 8 | `0xedf260` | 66 bytes |
| `CTickTask_UpdateAI` | `0x558ee00` | `0x4aaddf0` | `0x459f140` | 7 | `0x1575530` | 407 bytes |
| `CTickTask_UpdateStateTrades` | `0x556ff90` | `0x4a93490` | `0x4590c80` | 8 | `0x13b7bd0` | leaf/no matching `.pdata` start |
| `CTickTask_UpdatePopGrowth` | `0x556ae30` | `0x4a8fa50` | `0x458efd0` | 8 | `0x13a3020` | leaf/no matching `.pdata` start |
| `CTickTask_MergeSmallPops` | `0x556a248` | `0x4a8f848` | `0x458ee90` | 7 | `0x13aacd0` | 503 bytes |
| `CTickTask_RunScriptedTests` | `0x5558d30` | `0x4a7f730` | `0x4583910` | 7 | `0x1265990` | 701 bytes |

No performance conclusion should be drawn from static function size. A 66-byte tail virtual may dispatch substantial helper work, while a larger function may run rarely.

## Employment example

`CTickTask_UpdateEmployment` maps to this vtable:

```text
slot 0  0x13c2fe0
slot 1  0x3bf7200
slot 2  0x62d680
slot 3  0x3bf7270
slot 4  0x1808250
slot 5  0x62d680
slot 6  0x13b8310   <- unique class-specific final virtual
```

Static disassembly of `0x13b8310` shows nontrivial task-specific setup and iteration over game-state structures. This strengthens the interpretation that the final virtual is part of the concrete task implementation, but the project still avoids assigning an unproven source-level method name.

## Eight-slot family

A large subset of 8-slot TickTasks has:

```text
...
slot 6  0x7d76b0   <- shared by 69 classes
slot 7  <unique per class>
```

Examples include:

- `CTickTask_UpdateStatePopNeedCache`
- `CTickTask_RecalculateModifierNodes`
- `CTickTask_UpdateWorldMarket`
- `CTickTask_UpdateStateTrades`
- `CTickTask_UpdatePopGrowth`

This reinforces using the final slot rather than a hard-coded slot index when constructing the static map.

## Seven-slot family

For most seven-slot classes the unique final virtual is slot 6.

Examples:

- `CTickTask_UpdateEmployment` → `0x13b8310`
- `CTickTask_ProcessPopPurchases` → `0xee74b0`
- `CTickTask_UpdateAI` → `0x1575530`
- `CTickTask_MergeSmallPops` → `0x13aacd0`

## Why this matters

Before this pass, a future heavy-save benchmark could tell us:

`CTickTask_UpdateEmployment is expensive`

but moving from that string to executable code still required a broad reverse-engineering search.

Now the mapping path is deterministic:

```text
TickTask name from runtime CSV
        ↓
MSVC TypeDescriptor
        ↓
Complete Object Locator
        ↓
vtable
        ↓
unique class-specific tail virtual
        ↓
small native function/call-graph region to inspect
```

This means the first real benchmark can immediately feed a native reverse-engineering target without repeating broad string hunting.

## Limitations

The RTTI pass does not establish:

- exact source-level virtual method names,
- whether all runtime work occurs inside the tail virtual,
- task dependency edges,
- task execution frequency,
- whether a task parallelizes internally,
- whether its cost is compute, lock, memory, or child work.

Those remain runtime/profiler questions.

## Reproduction

```text
python tools/map_ticktask_rtti.py <Vic3_data.zip-or-install> \
  --output research/generated/ticktask-rtti-local.json
```

The full generated JSON is intentionally reproducible from the local executable. The repository keeps the methodology and high-value mappings rather than treating raw generated address data as hand-maintained source of truth.
