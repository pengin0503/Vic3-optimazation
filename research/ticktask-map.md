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
