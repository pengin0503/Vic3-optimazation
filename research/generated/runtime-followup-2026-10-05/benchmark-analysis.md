# Victoria 3 benchmark analysis

Measured runs: **3**

> Timing/lock metrics identify hotspots and correlation only; do not infer causality from one metric. Unknown variance is not zero noise; at least three matched runs per condition are required to assess repeatability. A low CV is not a significance test.

## Scaling

| Variant | Threads | Runs | Median wall-clock (s) | Speedup vs 1 thread | CV | Noise | Repeatability assessed |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| baseline-no-active-mods | 8 | 1 | 37.510 | n/a× | n/a% | unknown | no |
| baseline-no-active-mods | 12 | 1 | 36.670 | n/a× | n/a% | unknown | no |
| baseline-no-active-mods | 16 | 1 | 34.640 | n/a× | n/a% | unknown | no |

## baseline-no-active-mods — 8 task threads

Runs: 1; wall-clock median: 37.510s; CV: n/a%; noise: unknown; repeatability assessed: no

### Top 20 TickTasks by cumulative cost

| Task | Mean total ms | Mean calls | Max record ms | Longest lock ms | CV | Noise |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| HandleAutonomousInvestment | 1657.000 | 368.0 | 38.000 | 26.000 | n/a% | unknown |
| UpdatePopGrowth | 1371.000 | 92.0 | 19.000 | 13.000 | n/a% | unknown |
| RecalculateModifierNodes | 1004.000 | 368.0 | 25.000 | 13.000 | n/a% | unknown |
| ProcessEconomicMigration | 948.000 | 368.0 | 40.000 | 30.000 | n/a% | unknown |
| UpdateEmployment | 844.000 | 13.0 | 68.000 | 14.000 | n/a% | unknown |
| UpdateBuildingSpendingPriorities_Stage2 | 603.000 | 368.0 | 68.000 | 68.000 | n/a% | unknown |
| UpdateStateTrades | 512.000 | 13.0 | 49.000 | 16.000 | n/a% | unknown |
| UpdateWorldMarket | 443.000 | 13.0 | 51.000 | 51.000 | n/a% | unknown |
| UpdateJobSatisfaction | 368.000 | 368.0 | 1.000 | 1.000 | n/a% | unknown |
| UpdateAICountryGoalsAdjustments | 308.000 | 92.0 | 7.000 | 7.000 | n/a% | unknown |
| UpdateSpendingVariables | 303.000 | 368.0 | 36.000 | 36.000 | n/a% | unknown |
| WeeklyBuildingBudgetUpdate | 269.000 | 13.0 | 22.000 | 19.000 | n/a% | unknown |
| UpdateStatePopNeedCache | 257.000 | 13.0 | 21.000 | 21.000 | n/a% | unknown |
| UpdateAI | 256.000 | 368.0 | 22.000 | 21.000 | n/a% | unknown |
| PrepareNavyAIData | 249.000 | 368.0 | 5.000 | 5.000 | n/a% | unknown |
| AverageStandardOfLivingUpdate | 230.000 | 13.0 | 20.000 | 20.000 | n/a% | unknown |
| RecalcStatePopStatistics | 194.000 | 13.0 | 16.000 | 16.000 | n/a% | unknown |
| UpdatePopsInterestGroupsAndMovements | 189.000 | 92.0 | 3.000 | 3.000 | n/a% | unknown |
| ProcessPopPurchases | 180.000 | 13.0 | 16.000 | 16.000 | n/a% | unknown |
| UpdatePopLoyaltiesFromStandardOfLivingChanges | 168.000 | 13.0 | 13.000 | 13.000 | n/a% | unknown |

### Top 20 TickTasks by longest lock

| Task | Longest lock ms | Mean total ms | Mean calls |
| --- | ---: | ---: | ---: |
| UpdateBuildingSpendingPriorities_Stage2 | 68.000 | 603.000 | 368.0 |
| UpdateNationalAwakenings | 62.000 | 62.000 | 3.0 |
| UpdateWorldMarket | 51.000 | 443.000 | 13.0 |
| UpdateSpendingVariables | 36.000 | 303.000 | 368.0 |
| ProcessEconomicMigration | 30.000 | 948.000 | 368.0 |
| UpdateCivilWars | 29.000 | 29.000 | 13.0 |
| HandleAutonomousInvestment | 26.000 | 1657.000 | 368.0 |
| UpdateInterestGroupSupportForPoliticalMovements | 26.000 | 73.000 | 3.0 |
| CreateNewPoliticalMovements | 24.000 | 155.000 | 92.0 |
| UpdateAI | 21.000 | 256.000 | 368.0 |
| UpdateStatePopNeedCache | 21.000 | 257.000 | 13.0 |
| AverageStandardOfLivingUpdate | 20.000 | 230.000 | 13.0 |
| WeeklyBuildingBudgetUpdate | 19.000 | 269.000 | 13.0 |
| ProcessPopPurchases | 16.000 | 180.000 | 13.0 |
| RecalcStatePopStatistics | 16.000 | 194.000 | 13.0 |
| SpawnCulturalCommunities | 16.000 | 62.000 | 368.0 |
| UpdateStateTrades | 16.000 | 512.000 | 13.0 |
| MonthlyPulseJournalEntries | 14.000 | 129.000 | 3.0 |
| UpdateEmployment | 14.000 | 844.000 | 13.0 |
| RecalculateModifierNodes | 13.000 | 1004.000 | 368.0 |

## baseline-no-active-mods — 12 task threads

Runs: 1; wall-clock median: 36.670s; CV: n/a%; noise: unknown; repeatability assessed: no

### Top 20 TickTasks by cumulative cost

| Task | Mean total ms | Mean calls | Max record ms | Longest lock ms | CV | Noise |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| HandleAutonomousInvestment | 1579.000 | 368.0 | 37.000 | 20.000 | n/a% | unknown |
| UpdatePopGrowth | 1211.000 | 92.0 | 15.000 | 13.000 | n/a% | unknown |
| ProcessEconomicMigration | 958.000 | 368.0 | 46.000 | 36.000 | n/a% | unknown |
| RecalculateModifierNodes | 888.000 | 368.0 | 22.000 | 13.000 | n/a% | unknown |
| UpdateEmployment | 820.000 | 13.0 | 71.000 | 14.000 | n/a% | unknown |
| UpdateBuildingSpendingPriorities_Stage2 | 562.000 | 368.0 | 69.000 | 68.000 | n/a% | unknown |
| UpdateStateTrades | 473.000 | 13.0 | 50.000 | 16.000 | n/a% | unknown |
| UpdateWorldMarket | 415.000 | 13.0 | 49.000 | 49.000 | n/a% | unknown |
| UpdateAICountryGoalsAdjustments | 318.000 | 92.0 | 7.000 | 7.000 | n/a% | unknown |
| UpdateSpendingVariables | 295.000 | 368.0 | 36.000 | 36.000 | n/a% | unknown |
| PrepareNavyAIData | 259.000 | 368.0 | 4.000 | 4.000 | n/a% | unknown |
| UpdateAI | 251.000 | 368.0 | 24.000 | 24.000 | n/a% | unknown |
| UpdateStatePopNeedCache | 221.000 | 13.0 | 19.000 | 19.000 | n/a% | unknown |
| WeeklyBuildingBudgetUpdate | 216.000 | 13.0 | 18.000 | 15.000 | n/a% | unknown |
| AverageStandardOfLivingUpdate | 173.000 | 13.0 | 14.000 | 14.000 | n/a% | unknown |
| UpdatePopsInterestGroupsAndMovements | 168.000 | 92.0 | 3.000 | 3.000 | n/a% | unknown |
| RecalcStatePopStatistics | 158.000 | 13.0 | 13.000 | 13.000 | n/a% | unknown |
| CreateNewPoliticalMovements | 150.000 | 92.0 | 24.000 | 24.000 | n/a% | unknown |
| ProcessPopPurchases | 143.000 | 13.0 | 12.000 | 12.000 | n/a% | unknown |
| MonthlyPulseJournalEntries | 126.000 | 3.0 | 42.000 | 14.000 | n/a% | unknown |

### Top 20 TickTasks by longest lock

| Task | Longest lock ms | Mean total ms | Mean calls |
| --- | ---: | ---: | ---: |
| UpdateBuildingSpendingPriorities_Stage2 | 68.000 | 562.000 | 368.0 |
| UpdateNationalAwakenings | 51.000 | 51.000 | 3.0 |
| UpdateWorldMarket | 49.000 | 415.000 | 13.0 |
| ProcessEconomicMigration | 36.000 | 958.000 | 368.0 |
| UpdateSpendingVariables | 36.000 | 295.000 | 368.0 |
| UpdateCivilWars | 31.000 | 31.000 | 13.0 |
| CreateNewPoliticalMovements | 24.000 | 150.000 | 92.0 |
| UpdateAI | 24.000 | 251.000 | 368.0 |
| UpdateInterestGroupSupportForPoliticalMovements | 21.000 | 63.000 | 3.0 |
| HandleAutonomousInvestment | 20.000 | 1579.000 | 368.0 |
| UpdateStatePopNeedCache | 19.000 | 221.000 | 13.0 |
| SpawnCulturalCommunities | 16.000 | 61.000 | 368.0 |
| UpdateStateTrades | 16.000 | 473.000 | 13.0 |
| WeeklyBuildingBudgetUpdate | 15.000 | 216.000 | 13.0 |
| AverageStandardOfLivingUpdate | 14.000 | 173.000 | 13.0 |
| MonthlyPulseJournalEntries | 14.000 | 126.000 | 3.0 |
| UpdateEmployment | 14.000 | 820.000 | 13.0 |
| RecalcStatePopStatistics | 13.000 | 158.000 | 13.0 |
| RecalculateModifierNodes | 13.000 | 888.000 | 368.0 |
| UpdatePopGrowth | 13.000 | 1211.000 | 92.0 |

## baseline-no-active-mods — 16 task threads

Runs: 1; wall-clock median: 34.640s; CV: n/a%; noise: unknown; repeatability assessed: no

### Top 20 TickTasks by cumulative cost

| Task | Mean total ms | Mean calls | Max record ms | Longest lock ms | CV | Noise |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| HandleAutonomousInvestment | 1593.000 | 368.0 | 39.000 | 19.000 | n/a% | unknown |
| UpdatePopGrowth | 1200.000 | 92.0 | 17.000 | 13.000 | n/a% | unknown |
| ProcessEconomicMigration | 956.000 | 368.0 | 36.000 | 29.000 | n/a% | unknown |
| UpdateEmployment | 846.000 | 13.0 | 83.000 | 14.000 | n/a% | unknown |
| RecalculateModifierNodes | 845.000 | 368.0 | 21.000 | 13.000 | n/a% | unknown |
| UpdateBuildingSpendingPriorities_Stage2 | 546.000 | 368.0 | 54.000 | 54.000 | n/a% | unknown |
| UpdateStateTrades | 462.000 | 13.0 | 45.000 | 16.000 | n/a% | unknown |
| UpdateWorldMarket | 403.000 | 13.0 | 47.000 | 47.000 | n/a% | unknown |
| UpdateAICountryGoalsAdjustments | 312.000 | 92.0 | 7.000 | 7.000 | n/a% | unknown |
| UpdateSpendingVariables | 311.000 | 368.0 | 37.000 | 37.000 | n/a% | unknown |
| PrepareNavyAIData | 258.000 | 368.0 | 5.000 | 5.000 | n/a% | unknown |
| UpdateJobSatisfaction | 258.000 | 368.0 | 1.000 | 1.000 | n/a% | unknown |
| UpdateAI | 247.000 | 368.0 | 22.000 | 22.000 | n/a% | unknown |
| UpdateStatePopNeedCache | 219.000 | 13.0 | 20.000 | 20.000 | n/a% | unknown |
| WeeklyBuildingBudgetUpdate | 196.000 | 13.0 | 16.000 | 12.000 | n/a% | unknown |
| UpdatePopsInterestGroupsAndMovements | 181.000 | 92.0 | 2.000 | 2.000 | n/a% | unknown |
| AverageStandardOfLivingUpdate | 152.000 | 13.0 | 14.000 | 14.000 | n/a% | unknown |
| CreateNewPoliticalMovements | 152.000 | 92.0 | 23.000 | 23.000 | n/a% | unknown |
| RecalcStatePopStatistics | 143.000 | 13.0 | 12.000 | 12.000 | n/a% | unknown |
| ProcessPopPurchases | 142.000 | 13.0 | 12.000 | 12.000 | n/a% | unknown |

### Top 20 TickTasks by longest lock

| Task | Longest lock ms | Mean total ms | Mean calls |
| --- | ---: | ---: | ---: |
| UpdateNationalAwakenings | 57.000 | 57.000 | 3.0 |
| UpdateBuildingSpendingPriorities_Stage2 | 54.000 | 546.000 | 368.0 |
| UpdateWorldMarket | 47.000 | 403.000 | 13.0 |
| UpdateSpendingVariables | 37.000 | 311.000 | 368.0 |
| UpdateCivilWars | 30.000 | 30.000 | 13.0 |
| ProcessEconomicMigration | 29.000 | 956.000 | 368.0 |
| CreateNewPoliticalMovements | 23.000 | 152.000 | 92.0 |
| UpdateAI | 22.000 | 247.000 | 368.0 |
| UpdateStatePopNeedCache | 20.000 | 219.000 | 13.0 |
| HandleAutonomousInvestment | 19.000 | 1593.000 | 368.0 |
| UpdateInterestGroupSupportForPoliticalMovements | 19.000 | 56.000 | 3.0 |
| SpawnCulturalCommunities | 16.000 | 62.000 | 368.0 |
| UpdateStateTrades | 16.000 | 462.000 | 13.0 |
| AverageStandardOfLivingUpdate | 14.000 | 152.000 | 13.0 |
| MonthlyPulseJournalEntries | 14.000 | 129.000 | 3.0 |
| UpdateEmployment | 14.000 | 846.000 | 13.0 |
| RecalculateModifierNodes | 13.000 | 845.000 | 368.0 |
| UpdatePopGrowth | 13.000 | 1200.000 | 92.0 |
| ProcessPopPurchases | 12.000 | 142.000 | 13.0 |
| RecalcStatePopStatistics | 12.000 | 143.000 | 13.0 |

## Interpretation guardrails

- Treat `longest_lock` as a lead for OS-level wait profiling, not proof of root cause.
- A high-cost task may still scale well internally.
- Do not optimize differences smaller than benchmark noise.
- Simulation wall-clock throughput is the primary outcome; CPU utilization is diagnostic.
