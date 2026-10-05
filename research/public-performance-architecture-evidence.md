# Publicly documented Victoria 3 internals relevant to performance work

Date: 2026-10-05  
Target project: `pengin0503/Vic3-optimazation`  
Reference build in this repository: Victoria 3 Windows 1.14.5  
Reference executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Purpose

Preserve externally available information about Victoria 3's internal execution model that is useful for the native-performance project, and map it onto evidence already recovered from the supplied 1.14.5 executable.

This document is an evidence guide, not a claim that old developer-diary timings still describe 1.14.5. Historical architecture descriptions are used to interpret current static/runtime evidence, not to select a patch without measurement.

## Evidence classes

- **Official architecture**: Paradox developer diary describing implementation details.
- **Official/reproduced patch notes**: shipped optimization patterns in later Victoria 3 versions.
- **Upstream engineering evidence**: public issue filed by a Victoria 3 developer against a dependency.
- **Project-local evidence**: exact-build RTTI/vtable/disassembly/benchmark artifacts in this repository.

When public descriptions and project-local static analysis agree, confidence in the *role of a subsystem* increases. Runtime reachability, critical-path cost, waits and optimization benefit still require runtime evidence.

---

## 1. Tick model and TickTask dependency model

Paradox states that one Victoria 3 tick represents six in-game hours. Work is divided into regular, daily, weekly, monthly and yearly categories.

Simulation work is further divided into **TickTasks**. A TickTask contains:
- a distinct set of game-state operations,
- an execution cadence,
- dependencies on other TickTasks that must complete first.

Paradox explicitly showed the dependency graph through the console command `TickTask.Graph`.

### Project correspondence

The 1.14.5 executable in this project contains more than 260 `CTickTask_*` names. Current repository work has mapped 258 concrete classes to MSVC RTTI/vtables and preserves a class-specific tail virtual for each mapped class.

Relevant existing files:
- `research/ticktask-map.md`
- `research/ticktask-rtti-findings.md`
- `research/ticktask-vtable-semantics.md`
- `research/ticktask-dependency-static-map.md`
- `research/generated/ticktask-dependencies-1.14.5.json`

Static parent/child dataflow is **not** recovered yet. Calls, shared helpers and co-references are intentionally not promoted to dependency edges.

### Development implication

Continue treating TickTask timing as the aggregate runtime truth and native functions as correlation anchors. Do not infer a critical path from static call edges alone.

---

## 2. Thread roles and GameState/UI synchronization

Paradox describes these thread groups for Victoria 3:

- **Network/Session thread**: runs the game simulation and player commands.
- **Primary task threads**: parallelizable game-simulation work.
- **Main thread**: interface and graphics updates.
- **Render thread**: rendering.
- **Secondary task threads**: generally non-game-logic work such as graphics support or saving.

The official performance diary also identifies profiler regions called `CScopedGameStateRelease`. During these regions, the simulation pauses mutation of game state so interface/graphics work can safely read a consistent state. Paradox notes that these release points occur only between TickTasks or selected internal steps.

### Project correspondence

The exact build preserves multiple `gamestatetick.cpp` source-path strings and known scheduler/range-execution strings. Current static analysis has not recovered a symbol or RTTI name for `CScopedGameStateRelease`.

Relevant existing files:
- `research/binary-map.md`
- `research/preliminary-static-analysis.md`
- `research/scheduler-heuristic-static-analysis.md`

### Development implication

A future static pass may search synchronization/IAT callers and game-state-tick neighborhoods, but must label results as **GameState/UI synchronization candidates** unless direct evidence identifies `CScopedGameStateRelease`.

Runtime OS traces should distinguish:
- session-thread CPU execution,
- primary-worker execution,
- worker idle,
- lock/wait time,
- session-thread pauses correlated with UI/graphics activity.

Low aggregate CPU utilization by itself does not establish scheduler failure.

---

## 3. Employment is explicitly multi-stage

Paradox describes `UpdateEmployment` as having at least:

1. a **parallel pre-step**,
2. a **deterministic sorting step** to avoid multiplayer order-dependent OOS,
3. a **serial phase**.

The serial portion includes operations that cannot safely be parallelized in the same way, including global Pop-object creation/destruction and script execution.

### Project correspondence

Current 1.14.5 static work already recovered a structure consistent with this description:

- `CTickTask_UpdateEmployment` task-specific tail virtual: `0x13b8310`
- Prepare callback candidate
- CollectEmployment lambda/callback
- SortEmployment lambda/callback
- item-processing candidate
- common range dispatcher and heuristic relationship

Relevant existing files:
- `research/ticktask-vtable-semantics.md`
- `research/ticktask-callback-map.md`
- `research/ticktask-dispatch-static-map.md`
- `research/generated/dispatch-followup-2026-10-05/`

### Development implication

Do **not** use the direct duration of `0x13b8310` as "all Employment cost". Runtime instrumentation should keep at least these stages distinct:

- Prepare
- Collect candidate
- Sort candidate
- item/body candidate
- shared range runner
- scheduler heuristic
- aggregate built-in `UpdateEmployment` TickTask timing

A machine-readable stage map is useful now because it reduces ambiguity when OS traces or native-profiler traces arrive.

---

## 4. Modifier Nodes are a Stellaris-like dependency system

Paradox states that Victoria 3 uses a system similar to Stellaris called **modifier nodes**.

The described behavior is:
- modifier dependencies are represented as a dependency structure,
- changed inputs mark nodes dirty,
- only dirty nodes and dependent nodes need recalculation,
- nodes can be partitioned into dependency-respecting batches,
- modifier-node calculations were parallelized as a major historical optimization.

The same official diary identifies modifier updating as one of the historically expensive TickTasks.

### Project correspondence

The exact 1.14.5 build contains:

- `CTickTask_RecalculateModifierNodes`
- unique vtable candidate: `0x44d8f58`
- class-specific tail virtual: `0x7da740`
- runtime timing evidence in the preserved benchmark set
- `modifier.cpp` source-path strings

A preserved benchmark report shows `RecalculateModifierNodes` as a material measured task in the current sample, not merely a historical candidate.

Relevant existing files:
- `research/ticktask-map.md`
- `research/ticktask-rtti-findings.md`
- `docs/superpowers/reports/vic3-benchmark-review-2026-10-05-ja.md`

### Development implication

This is the clearest new offline target from the public-source review.

Without changing the game, the project can immediately:
- generate a bounded call/reference graph from `CTickTask_RecalculateModifierNodes`,
- record direct calls, tail jumps, indirect sites, code-address materialization and validated RTTI/vtables separately,
- check whether known common dispatcher/range helpers appear within the bounded graph,
- preserve exact-build selected regions and hashes,
- prepare explicit targets for later OS/native trace correlation.

Do not infer dirty-propagation semantics from offsets alone.

---

## 5. Scheduler heuristic matches current static findings

Paradox explains that per-country work can vary by more than two orders of magnitude. A naive even split can leave one worker with several expensive countries while other workers become idle.

Their described mitigation allows TickTasks to provide heuristic cost information. The scheduler identifies outliers using dispersion in expected computation time and schedules expensive work separately.

### Project correspondence

Current exact-build static analysis recovered:

- string `MaybeRunRangeExecutionParallelWithHeuristic`
- native region `0x7db150–0x7dba91`
- caller/range runner around `0x7dbaa0`
- common dispatcher candidate around `0x7dc160`
- observed calculations of min, max, mean, variance, square root and approximately `mean + 2*stddev`
- early rejection paths and range-size checks

Relevant existing file:
- `research/scheduler-heuristic-static-analysis.md`

### Development implication

The public architecture description strongly supports the current interpretation of the heuristic family, but does not prove it is the 1.14.5 bottleneck.

Keep first runtime instrumentation read-only and record:
- range length,
- task thread count,
- decision,
- work/chunk count,
- historical/heuristic statistics already present at the decision point,
- caller/target identity,
- thread and timestamp.

Never force the return value before runtime evidence.

---

## 6. Pop-object count, not only population, is a first-order performance variable

Paradox states that Employment cost is strongly correlated with the **number of Pop objects**, not total population.

Update 1.10 later shipped changes aimed at reducing late-game Pop-object fragmentation. The patch notes state that late-game Pop count was reduced by roughly 25% through rules that:
- limit culture/religion combinations per profession/building according to workforce size,
- fire smaller Pops first,
- prefer hiring Pops already present in the building,
- batch migrations into groups of at least roughly 1,000 people.

### Development implication

For save-based performance research, track:
- total Pop-object count,
- tiny-Pop count/distribution,
- Pops per state,
- Pops per workplace/building,
- profession/culture/religion fragmentation,
- migration-induced fragmentation.

Do not use total population alone as the independent variable for Employment performance.

This project should not reduce simulated diversity merely to gain speed unless explicitly offered as an optional gameplay-changing mode. Pop topology is still useful as an explanatory/control variable.

---

## 7. Cache, precompute, skip and parallelize are recurring official optimization patterns

Recent shipped changes show the same optimization families repeatedly.

### Update 1.10

Besides Pop-object reduction, the AI:
- remembers temporarily when a country is completely uninterested in a sway offer,
- skips evaluating sway offers for countries that cannot support them.

This is a combination of cache plus early rejection.

### Hotfix 1.13.5

The performance section includes:
- optimized supply computation,
- optimized `UpdatePartySupport` TickTask,
- cached modifier names,
- parallel country sea-node range-distance updates,
- precomputed ideology law stances,
- cached AI willingness to prepare for war,
- cached expensive Diplomatic Play variables,
- reduced cost of AI Diplomatic Action evaluation.

### Hotfix 1.13.9

Paradox reports:
- memory use reduced by about 7–10%,
- total allocations reduced by 15%,
- additional overall tick-speed improvements.

### Development implication

When a measured hotspot is selected, consider these remedy classes before attempting risky scheduler/global behavior changes:

1. **Skip** work for objects that cannot affect the result.
2. **Throttle** updates when exact semantics permit lower cadence.
3. **Cache** expensive derived values until invalidated.
4. **Precompute** stable decision inputs.
5. **Reduce invalidation fan-out** without changing results.
6. **Parallelize** safe pre-steps or independent batches.
7. **Reduce allocation/object churn**.
8. **Reduce UI/GameState contention** where OS traces prove it matters.

The patch type must follow the measured bottleneck class.

---

## 8. Memory allocator evidence and PdxNew anchor

Paradox's 1.2 performance diary states that Clausewitz moved general allocation work to **mimalloc**, with an observed around-4% gain in the test described there.

A public mimalloc issue filed by a Victoria 3 developer states that Victoria 3 uses mimalloc from version 1.2 onward and includes this stack fragment:

```text
mi_heap_malloc
mi_heap_alloc_new
mi_new
PdxNew(unsigned long) pdx_allocator.cpp:223
operator new(unsigned long) pdx_allocator.cpp:288
```

### Development implication

Allocation is a legitimate analysis axis, especially because 1.13.9 later reduced total allocations by 15%.

However, hooking every allocation on a hot game run can create severe observer overhead. Prefer OS/allocator profiling first. If a native allocation probe is later required, constrain it by selected native target/thread/window rather than globally logging every allocation.

---

## 9. Source-backed priority changes for this repository

The public-source review changes priorities as follows.

### S: implementable offline now

1. **Dedicated ModifierNode static follow-up**
   - seed from `CTickTask_RecalculateModifierNodes` / RTTI, not a guessed address;
   - bounded graph only;
   - exact-build fail-closed;
   - generated machine-readable evidence + concise analysis;
   - no hook and no state write.

2. **Employment stage target map**
   - convert already recovered Prepare/Collect/Sort/item candidates into a stable machine-readable exact-build target map;
   - preserve evidence provenance and runtime-unverified state;
   - make future OS/native traces easy to correlate.

3. **GameState/UI synchronization candidate inventory**
   - enumerate relevant imported synchronization primitives and validated caller sites;
   - intersect where possible with game-state-tick/scheduler regions;
   - do not name a function `CScopedGameStateRelease` without direct evidence.

### A: do after runtime/OS evidence or as bounded supporting work

- allocation hotspots scoped to selected targets,
- Pop topology analysis from a representative save,
- deeper ModifierNode dirty-propagation reverse engineering,
- full Employment serial-commit reverse engineering.

### Blocked by runtime evidence

- scheduler override,
- changing heuristic thresholds,
- changing simulation cadence,
- lock removal,
- Employment parallelization,
- state mutation,
- native performance patch.

---

## 10. Guardrails

Public architecture descriptions are not stable APIs.

For every exact-build result:
- gate on executable SHA-256,
- prefer RTTI/signature/section/control-flow evidence over raw addresses,
- record uncertainty explicitly,
- distinguish direct call, tail jump, code-address materialization and vtable reference,
- distinguish source-backed semantics from inferred field names,
- keep runtime reachability/critical-path/benefit claims separate.

For version updates:
- rerun `tools/analyze_vic3.py`,
- rerun `tools/map_ticktask_rtti.py`,
- compare with `tools/compare_static_analysis.py`,
- regenerate signatures,
- leave unknown-build hooks disabled.

---

## Sources

### Official architecture

- Paradox Interactive, **Dev Diary #76 - Performance**  
  https://www.paradoxinteractive.com/games/victoria-3/news/dev-diary-76-performance

This is the primary source for:
- six-hour ticks and cadence classes,
- TickTask dependencies and `TickTask.Graph`,
- thread roles,
- `CScopedGameStateRelease`,
- Employment parallel/sort/serial stages,
- Stellaris-like Modifier Nodes,
- heuristic scheduling for uneven work,
- Pop-object-count performance,
- mimalloc adoption/performance.

### Shipped performance changes

- Victoria 3 Update 1.10 patch notes, mirrored by SteamDB  
  https://steamdb.info/patchnotes/20016792/

- Victoria 3 Hotfix 1.13.5 patch notes, mirrored by SteamDB  
  https://steamdb.info/patchnotes/23198929/

- Victoria 3 Hotfix 1.13.9 patch notes, mirrored by SteamDB  
  https://steamdb.info/patchnotes/23897342/

### Upstream allocator evidence

- microsoft/mimalloc issue #807, filed by a Victoria 3 developer  
  https://github.com/microsoft/mimalloc/issues/807

## Re-evaluation rule

Revisit this note when:
- the target executable changes,
- Paradox publishes a newer performance/engine explanation,
- runtime evidence contradicts a historical architecture assumption,
- a current source shows that an old implementation was replaced.

