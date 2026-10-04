# TickTask map — Victoria 3 1.14.5

The executable exposes 260 unique `CTickTask_*` names. The complete inventory is in `research/generated/ticktasks-1.14.5.txt`.

This file groups only the performance-relevant families needed for later runtime correlation. No task is considered a hotspot until measured.

## Population / employment

- `CTickTask_UpdateEmployment`
- `CTickTask_UpdateHiringRates`
- `CTickTask_UpdateUnemploymentProfessionTransitions`
- `CTickTask_UpdatePopGrowth`
- `CTickTask_UpdatePopLiteracy`
- `CTickTask_UpdatePopPoliticalStrength`
- `CTickTask_UpdatePopsInterestGroupsAndMovements`
- `CTickTask_MergeSmallPops`
- `CTickTask_ProcessPopPurchases`
- `CTickTask_UpdateStatePopNeedCache`
- `CTickTask_UpdateMarketCachedPopNeedExpenses`

Relevant source anchors include `employment_helper.cpp`, `employment_utils.cpp`, `pop.cpp`, and `popmanager.cpp`.

## Modifier / cached-state recalculation

- `CTickTask_RecalculateModifierNodes`
- `CTickTask_UpdateStandardBuildingModifiers`
- `CTickTask_UpdateCachedCompanyProductivity`
- `CTickTask_UpdateCachedEconomicDependence`
- `CTickTask_UpdateCachedLiteracy`
- `CTickTask_UpdateCachedRankingsAndGlobalGDP`

Relevant source anchor: `modifier.cpp`.

## Market / trade

- `CTickTask_UpdateWorldMarket`
- `CTickTask_UpdateStateTrades`
- `CTickTask_UpdatePriceReports`
- `CTickTask_UpdateProducedSupply`
- `CTickTask_UpdateGoodsLeaderboards`
- `CTickTask_ValidateGoodsTaxesAndTariffs`
- `CTickTask_UpdateMarketCachedPopNeedExpenses`

Relevant source anchors: `market.cpp`, `world_market.cpp`.

## AI

- `CTickTask_UpdateAI`
- `CTickTask_UpdateAIGoals`
- `CTickTask_UpdateAIStrategies`
- `CTickTask_UpdateAIMemories`
- `CTickTask_UpdateAIRegionalObjectives`
- `CTickTask_RecalcAIRegionScores`
- `CTickTask_UpdateNavyAI`
- `CTickTask_UpdateNavyAIShipTemplates`

## Budget / buildings

- `CTickTask_DailyCountryBudgetUpdate`
- `CTickTask_WeeklyBuildingBudgetUpdate`
- `CTickTask_WeeklyStateBudgetUpdate`
- `CTickTask_ProcessWagesStage1`
- `CTickTask_ProcessWagesStage2`
- `CTickTask_UpdateBuildingSpendingPriorities_Stage1`
- `CTickTask_UpdateBuildingSpendingPriorities_Stage2`
- `CTickTask_UpdateBuildingThroughput`
- `CTickTask_HandleAutonomousInvestment`
- `CTickTask_ProgressConstructionQueues`

## Runtime fields to attach later

For each measured task, extend this document with:

| Field | Meaning |
| --- | --- |
| cumulative ms | sum over fixed benchmark interval |
| calls | built-in profiler call count |
| longest lock | built-in lock timing lead |
| scaling | change across TaskThreadCount matrix |
| OS evidence | WPR/uProf thread/wait/cache evidence |
| code mapping | candidate native function(s) |
| confidence | low / medium / high |
| patch candidate | no / safe / experimental |

The first native target must be selected from measured data, not from task name or intuition.


## Static native anchors from MSVC RTTI

The RTTI/vtable pass maps **258 of 260** exposed TickTask names to concrete class vtables. See `research/ticktask-rtti-findings.md`.

The final virtual slot is unique for all 258 mapped classes and is therefore recorded as a **task-specific tail virtual**. This is a code anchor only; its source-level method name is not yet proven.

| TickTask | Vtable RVA | Task-specific tail virtual |
| --- | ---: | ---: |
| `CTickTask_UpdateEmployment` | `0x4590800` | `0x13b8310` |
| `CTickTask_UpdateStatePopNeedCache` | `0x4590dd8` | `0x13b7e70` |
| `CTickTask_ProcessPopPurchases` | `0x4550fd8` | `0xee74b0` |
| `CTickTask_RecalculateModifierNodes` | `0x44d8f58` | `0x7da740` |
| `CTickTask_UpdateWorldMarket` | `0x4551108` | `0xedf260` |
| `CTickTask_UpdateAI` | `0x459f140` | `0x1575530` |
| `CTickTask_UpdateStateTrades` | `0x4590c80` | `0x13b7bd0` |
| `CTickTask_UpdatePopGrowth` | `0x458efd0` | `0x13a3020` |
| `CTickTask_MergeSmallPops` | `0x458ee90` | `0x13aacd0` |

The two exposed names without a matching concrete TickTask RTTI TypeDescriptor in this build are:

- `CTickTask_CheckNonFulfillments`
- `CTickTask_MoveFormations`

When real runtime timings arrive, the profiler task name can now be mapped directly to a small native code region rather than starting a broad binary search.
