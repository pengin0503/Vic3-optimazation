# TickTask native-target triage

Variant: **user-3month-repeat-batch**
Task threads: **12**

> This output joins runtime cost/lock evidence to static code anchors. It does not prove root cause or make a patch safe.

## Top by cumulative cost

| Task | Mean total ms | Longest lock ms | Native tail anchor | Mapping |
| --- | ---: | ---: | ---: | --- |
| HandleAutonomousInvestment | 1617.000 | 22.000 | 0xf6e590 | yes |
| UpdatePopGrowth | 1229.000 | 13.000 | 0x13a3020 | yes |
| ProcessEconomicMigration | 966.333 | 33.000 | 0x11b0c00 | yes |
| RecalculateModifierNodes | 875.000 | 13.000 | 0x7da740 | yes |
| UpdateEmployment | 841.000 | 14.000 | 0x13b8310 | yes |
| UpdateBuildingSpendingPriorities_Stage2 | 563.000 | 67.000 | 0x157cbd0 | yes |
| UpdateStateTrades | 473.667 | 16.000 | 0x13b7bd0 | yes |
| UpdateWorldMarket | 414.000 | 48.000 | 0xedf260 | yes |
| UpdateAICountryGoalsAdjustments | 315.000 | 7.000 | 0x1576300 | yes |
| UpdateSpendingVariables | 308.000 | 45.000 | 0x1575af0 | yes |
| PrepareNavyAIData | 260.000 | 5.000 | 0x157d990 | yes |
| UpdateAI | 254.000 | 22.000 | 0x1575530 | yes |
| UpdateStatePopNeedCache | 218.667 | 18.000 | 0x13b7e70 | yes |
| WeeklyBuildingBudgetUpdate | 217.333 | 14.000 | 0xf48e20 | yes |
| AverageStandardOfLivingUpdate | 173.333 | 15.000 | 0xf5e490 | yes |
| UpdatePopsInterestGroupsAndMovements | 168.333 | 3.000 | 0x13a3000 | yes |
| CreateNewPoliticalMovements | 160.667 | 24.000 | 0x13f54e0 | yes |
| RecalcStatePopStatistics | 160.333 | 13.000 | 0x13c1510 | yes |
| ProcessPopPurchases | 142.333 | 12.000 | 0xee74b0 | yes |
| MonthlyPulseJournalEntries | 129.333 | 14.000 | 0x10032a0 | yes |

## Top by longest lock

| Task | Longest lock ms | Mean total ms | Native tail anchor | Mapping |
| --- | ---: | ---: | ---: | --- |
| UpdateBuildingSpendingPriorities_Stage2 | 67.000 | 563.000 | 0x157cbd0 | yes |
| UpdateNationalAwakenings | 52.000 | 52.000 | 0xf17500 | yes |
| UpdateWorldMarket | 48.000 | 414.000 | 0xedf260 | yes |
| UpdateSpendingVariables | 45.000 | 308.000 | 0x1575af0 | yes |
| ProcessEconomicMigration | 33.000 | 966.333 | 0x11b0c00 | yes |
| UpdateCivilWars | 32.000 | 30.333 | 0xf8fad0 | yes |
| CreateNewPoliticalMovements | 24.000 | 160.667 | 0x13f54e0 | yes |
| HandleAutonomousInvestment | 22.000 | 1617.000 | 0xf6e590 | yes |
| UpdateAI | 22.000 | 254.000 | 0x1575530 | yes |
| UpdateInterestGroupSupportForPoliticalMovements | 21.000 | 59.000 | 0x13f4e80 | yes |
| SpawnCulturalCommunities | 18.000 | 63.667 | 0xf13300 | yes |
| UpdateStatePopNeedCache | 18.000 | 218.667 | 0x13b7e70 | yes |
| UpdateStateTrades | 16.000 | 473.667 | 0x13b7bd0 | yes |
| AverageStandardOfLivingUpdate | 15.000 | 173.333 | 0xf5e490 | yes |
| MonthlyPulseJournalEntries | 14.000 | 129.333 | 0x10032a0 | yes |
| UpdateEmployment | 14.000 | 841.000 | 0x13b8310 | yes |
| WeeklyBuildingBudgetUpdate | 14.000 | 217.333 | 0xf48e20 | yes |
| RecalcStatePopStatistics | 13.000 | 160.333 | 0x13c1510 | yes |
| RecalculateModifierNodes | 13.000 | 875.000 | 0x7da740 | yes |
| UpdatePopGrowth | 13.000 | 1229.000 | 0x13a3020 | yes |

## Interpretation

- High cumulative cost identifies where time is spent, not why.
- High longest_lock is a lead for WPR/WPA wait analysis, not proof of lock-contention root cause.
- A mapped tail virtual is a reverse-engineering entry point; its source-level method name is not assumed.
- No native patch should be selected until scaling and OS-level evidence agree with the hotspot.
