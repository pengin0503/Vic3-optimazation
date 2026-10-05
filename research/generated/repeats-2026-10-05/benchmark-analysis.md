# Victoria 3 benchmark analysis

Measured runs: **9**

> Timing/lock metrics identify hotspots and correlation only; do not infer causality from one metric. Unknown variance is not zero noise; at least three matched runs per condition are required to assess repeatability. A low CV is not a significance test.

## Scaling

| Variant | Threads | Runs | Median wall-clock (s) | Speedup vs 1 thread | CV | Noise | Repeatability assessed |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| user-3month-repeat-batch | 8 | 3 | 36.880 | n/a× | 1.03% | no | yes |
| user-3month-repeat-batch | 12 | 3 | 34.530 | n/a× | 0.58% | no | yes |
| user-3month-repeat-batch | 16 | 3 | 34.660 | n/a× | 0.82% | no | yes |

## user-3month-repeat-batch — 8 task threads

Runs: 3; wall-clock median: 36.880s; CV: 1.03%; noise: no; repeatability assessed: yes

### Top 20 TickTasks by cumulative cost

| Task | Mean total ms | Mean calls | Max record ms | Longest lock ms | CV | Noise |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| HandleAutonomousInvestment | 1664.333 | 368.0 | 41.000 | 26.000 | 1.50% | no |
| UpdatePopGrowth | 1387.667 | 92.0 | 20.000 | 14.000 | 1.59% | no |
| RecalculateModifierNodes | 1010.333 | 368.0 | 26.000 | 13.000 | 2.09% | no |
| ProcessEconomicMigration | 959.667 | 368.0 | 45.000 | 33.000 | 1.14% | no |
| UpdateEmployment | 846.667 | 13.0 | 71.000 | 15.000 | 1.19% | no |
| UpdateBuildingSpendingPriorities_Stage2 | 626.000 | 368.0 | 93.000 | 93.000 | 2.25% | no |
| UpdateStateTrades | 520.667 | 13.0 | 53.000 | 19.000 | 1.60% | no |
| UpdateWorldMarket | 453.000 | 13.0 | 53.000 | 53.000 | 2.11% | no |
| UpdateJobSatisfaction | 363.000 | 368.0 | 1.000 | 1.000 | 0.95% | no |
| UpdateAICountryGoalsAdjustments | 322.000 | 92.0 | 8.000 | 8.000 | 1.61% | no |
| UpdateSpendingVariables | 300.667 | 368.0 | 43.000 | 43.000 | 3.23% | yes |
| WeeklyBuildingBudgetUpdate | 276.333 | 13.0 | 23.000 | 20.000 | 1.27% | no |
| UpdateStatePopNeedCache | 261.000 | 13.0 | 24.000 | 24.000 | 1.67% | no |
| UpdateAI | 256.000 | 368.0 | 22.000 | 22.000 | 8.46% | yes |
| PrepareNavyAIData | 250.000 | 368.0 | 5.000 | 5.000 | 2.23% | no |
| AverageStandardOfLivingUpdate | 229.667 | 13.0 | 21.000 | 21.000 | 1.76% | no |
| RecalcStatePopStatistics | 206.667 | 13.0 | 18.000 | 18.000 | 1.83% | no |
| UpdatePopsInterestGroupsAndMovements | 193.000 | 92.0 | 3.000 | 3.000 | 1.37% | no |
| ProcessPopPurchases | 185.667 | 13.0 | 16.000 | 16.000 | 2.97% | no |
| UpdatePopLoyaltiesFromStandardOfLivingChanges | 169.000 | 13.0 | 14.000 | 14.000 | 0.59% | no |

### Top 20 TickTasks by longest lock

| Task | Longest lock ms | Mean total ms | Mean calls |
| --- | ---: | ---: | ---: |
| UpdateBuildingSpendingPriorities_Stage2 | 93.000 | 626.000 | 368.0 |
| UpdateNationalAwakenings | 62.000 | 61.000 | 3.0 |
| UpdateWorldMarket | 53.000 | 453.000 | 13.0 |
| UpdateSpendingVariables | 43.000 | 300.667 | 368.0 |
| UpdateCivilWars | 34.000 | 31.667 | 13.0 |
| ProcessEconomicMigration | 33.000 | 959.667 | 368.0 |
| UpdateInterestGroupSupportForPoliticalMovements | 30.000 | 79.333 | 3.0 |
| HandleAutonomousInvestment | 26.000 | 1664.333 | 368.0 |
| CreateNewPoliticalMovements | 24.000 | 155.667 | 92.0 |
| UpdateStatePopNeedCache | 24.000 | 261.000 | 13.0 |
| UpdateAI | 22.000 | 256.000 | 368.0 |
| AverageStandardOfLivingUpdate | 21.000 | 229.667 | 13.0 |
| WeeklyBuildingBudgetUpdate | 20.000 | 276.333 | 13.0 |
| UpdateStateTrades | 19.000 | 520.667 | 13.0 |
| RecalcStatePopStatistics | 18.000 | 206.667 | 13.0 |
| SpawnCulturalCommunities | 17.000 | 62.333 | 368.0 |
| ProcessPopPurchases | 16.000 | 185.667 | 13.0 |
| UpdateEmployment | 15.000 | 846.667 | 13.0 |
| MonthlyPulseJournalEntries | 14.000 | 128.000 | 3.0 |
| UpdatePopGrowth | 14.000 | 1387.667 | 92.0 |

## user-3month-repeat-batch — 12 task threads

Runs: 3; wall-clock median: 34.530s; CV: 0.58%; noise: no; repeatability assessed: yes

### Top 20 TickTasks by cumulative cost

| Task | Mean total ms | Mean calls | Max record ms | Longest lock ms | CV | Noise |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| HandleAutonomousInvestment | 1617.000 | 369.0 | 40.000 | 22.000 | 0.73% | no |
| UpdatePopGrowth | 1229.000 | 92.3 | 17.000 | 13.000 | 1.27% | no |
| ProcessEconomicMigration | 966.333 | 369.0 | 43.000 | 33.000 | 1.04% | no |
| RecalculateModifierNodes | 875.000 | 369.0 | 23.000 | 13.000 | 0.71% | no |
| UpdateEmployment | 841.000 | 13.0 | 73.000 | 14.000 | 0.78% | no |
| UpdateBuildingSpendingPriorities_Stage2 | 563.000 | 369.0 | 67.000 | 67.000 | 1.42% | no |
| UpdateStateTrades | 473.667 | 13.0 | 46.000 | 16.000 | 0.12% | no |
| UpdateWorldMarket | 414.000 | 13.0 | 48.000 | 48.000 | 0.42% | no |
| UpdateAICountryGoalsAdjustments | 315.000 | 92.3 | 7.000 | 7.000 | 1.10% | no |
| UpdateSpendingVariables | 308.000 | 369.0 | 45.000 | 45.000 | 2.77% | no |
| PrepareNavyAIData | 260.000 | 369.0 | 5.000 | 5.000 | 3.42% | yes |
| UpdateAI | 254.000 | 369.0 | 22.000 | 22.000 | 4.00% | yes |
| UpdateStatePopNeedCache | 218.667 | 13.0 | 18.000 | 18.000 | 1.73% | no |
| WeeklyBuildingBudgetUpdate | 217.333 | 13.0 | 18.000 | 14.000 | 1.06% | no |
| AverageStandardOfLivingUpdate | 173.333 | 13.0 | 15.000 | 15.000 | 0.88% | no |
| UpdatePopsInterestGroupsAndMovements | 168.333 | 92.3 | 3.000 | 3.000 | 3.05% | yes |
| CreateNewPoliticalMovements | 160.667 | 92.3 | 24.000 | 24.000 | 7.78% | yes |
| RecalcStatePopStatistics | 160.333 | 13.0 | 13.000 | 13.000 | 1.57% | no |
| ProcessPopPurchases | 142.333 | 13.0 | 12.000 | 12.000 | 0.81% | no |
| MonthlyPulseJournalEntries | 129.333 | 3.0 | 44.000 | 14.000 | 0.45% | no |

### Top 20 TickTasks by longest lock

| Task | Longest lock ms | Mean total ms | Mean calls |
| --- | ---: | ---: | ---: |
| UpdateBuildingSpendingPriorities_Stage2 | 67.000 | 563.000 | 369.0 |
| UpdateNationalAwakenings | 52.000 | 52.000 | 3.0 |
| UpdateWorldMarket | 48.000 | 414.000 | 13.0 |
| UpdateSpendingVariables | 45.000 | 308.000 | 369.0 |
| ProcessEconomicMigration | 33.000 | 966.333 | 369.0 |
| UpdateCivilWars | 32.000 | 30.333 | 13.0 |
| CreateNewPoliticalMovements | 24.000 | 160.667 | 92.3 |
| HandleAutonomousInvestment | 22.000 | 1617.000 | 369.0 |
| UpdateAI | 22.000 | 254.000 | 369.0 |
| UpdateInterestGroupSupportForPoliticalMovements | 21.000 | 59.000 | 3.0 |
| SpawnCulturalCommunities | 18.000 | 63.667 | 369.0 |
| UpdateStatePopNeedCache | 18.000 | 218.667 | 13.0 |
| UpdateStateTrades | 16.000 | 473.667 | 13.0 |
| AverageStandardOfLivingUpdate | 15.000 | 173.333 | 13.0 |
| MonthlyPulseJournalEntries | 14.000 | 129.333 | 3.0 |
| UpdateEmployment | 14.000 | 841.000 | 13.0 |
| WeeklyBuildingBudgetUpdate | 14.000 | 217.333 | 13.0 |
| RecalcStatePopStatistics | 13.000 | 160.333 | 13.0 |
| RecalculateModifierNodes | 13.000 | 875.000 | 369.0 |
| UpdatePopGrowth | 13.000 | 1229.000 | 92.3 |

## user-3month-repeat-batch — 16 task threads

Runs: 3; wall-clock median: 34.660s; CV: 0.82%; noise: no; repeatability assessed: yes

### Top 20 TickTasks by cumulative cost

| Task | Mean total ms | Mean calls | Max record ms | Longest lock ms | CV | Noise |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| HandleAutonomousInvestment | 1623.333 | 368.0 | 44.000 | 23.000 | 0.43% | no |
| UpdatePopGrowth | 1228.667 | 92.0 | 18.000 | 13.000 | 1.11% | no |
| ProcessEconomicMigration | 984.333 | 368.0 | 43.000 | 32.000 | 1.56% | no |
| UpdateEmployment | 855.333 | 13.0 | 78.000 | 15.000 | 0.86% | no |
| RecalculateModifierNodes | 846.667 | 368.0 | 22.000 | 12.000 | 1.61% | no |
| UpdateBuildingSpendingPriorities_Stage2 | 546.667 | 368.0 | 53.000 | 53.000 | 1.83% | no |
| UpdateStateTrades | 465.333 | 13.0 | 47.000 | 16.000 | 0.87% | no |
| UpdateWorldMarket | 408.333 | 13.0 | 48.000 | 48.000 | 0.51% | no |
| UpdateAICountryGoalsAdjustments | 321.333 | 92.0 | 7.000 | 7.000 | 1.18% | no |
| UpdateSpendingVariables | 307.333 | 368.0 | 36.000 | 36.000 | 2.12% | no |
| PrepareNavyAIData | 264.667 | 368.0 | 5.000 | 5.000 | 1.86% | no |
| UpdateAI | 258.000 | 368.0 | 22.000 | 22.000 | 3.03% | yes |
| UpdateJobSatisfaction | 233.000 | 368.0 | 1.000 | 1.000 | 8.22% | yes |
| UpdateStatePopNeedCache | 210.000 | 13.0 | 19.000 | 19.000 | 1.72% | no |
| WeeklyBuildingBudgetUpdate | 202.667 | 13.0 | 17.000 | 17.000 | 1.59% | no |
| UpdatePopsInterestGroupsAndMovements | 181.667 | 92.0 | 3.000 | 3.000 | 1.15% | no |
| AverageStandardOfLivingUpdate | 156.333 | 13.0 | 16.000 | 16.000 | 2.06% | no |
| CreateNewPoliticalMovements | 153.667 | 92.0 | 24.000 | 24.000 | 0.75% | no |
| RecalcStatePopStatistics | 143.333 | 13.0 | 14.000 | 14.000 | 0.81% | no |
| ProcessPopPurchases | 138.000 | 13.0 | 12.000 | 12.000 | 1.26% | no |

### Top 20 TickTasks by longest lock

| Task | Longest lock ms | Mean total ms | Mean calls |
| --- | ---: | ---: | ---: |
| UpdateNationalAwakenings | 59.000 | 57.000 | 3.0 |
| UpdateBuildingSpendingPriorities_Stage2 | 53.000 | 546.667 | 368.0 |
| UpdateWorldMarket | 48.000 | 408.333 | 13.0 |
| UpdateSpendingVariables | 36.000 | 307.333 | 368.0 |
| ProcessEconomicMigration | 32.000 | 984.333 | 368.0 |
| UpdateCivilWars | 31.000 | 30.333 | 13.0 |
| CreateNewPoliticalMovements | 24.000 | 153.667 | 92.0 |
| HandleAutonomousInvestment | 23.000 | 1623.333 | 368.0 |
| UpdateAI | 22.000 | 258.000 | 368.0 |
| UpdateInterestGroupSupportForPoliticalMovements | 21.000 | 57.667 | 3.0 |
| UpdateStatePopNeedCache | 19.000 | 210.000 | 13.0 |
| SpawnCulturalCommunities | 17.000 | 63.333 | 368.0 |
| WeeklyBuildingBudgetUpdate | 17.000 | 202.667 | 13.0 |
| AverageStandardOfLivingUpdate | 16.000 | 156.333 | 13.0 |
| UpdateStateTrades | 16.000 | 465.333 | 13.0 |
| UpdateColonizationProgress | 15.000 | 100.667 | 92.0 |
| UpdateEmployment | 15.000 | 855.333 | 13.0 |
| MonthlyPulseJournalEntries | 14.000 | 131.667 | 3.0 |
| RecalcStatePopStatistics | 14.000 | 143.333 | 13.0 |
| UpdatePopGrowth | 13.000 | 1228.667 | 92.0 |

## Interpretation guardrails

- Treat `longest_lock` as a lead for OS-level wait profiling, not proof of root cause.
- A high-cost task may still scale well internally.
- Do not optimize differences smaller than benchmark noise.
- Simulation wall-clock throughput is the primary outcome; CPU utilization is diagnostic.
