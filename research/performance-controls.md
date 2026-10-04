# Performance-relevant controls in shipped Victoria 3 1.14.5 data

Date: 2026-10-04

This inventory is derived from the supplied `game/common/defines` and game-rule data.

It exists for two reasons:

1. identify controls Paradox itself treats as performance-sensitive,
2. provide controlled A/B experiments after the native baseline exists.

These are **not** the primary optimization plan. Many change simulation frequency, search breadth, or Pop consolidation and therefore can change gameplay semantics.

## Journal Entry update frequency

From `game/common/defines/00_defines.txt`:

| Define | Vanilla |
| --- | ---: |
| `JOURNAL_ENTRY_UPDATE_ACTIVE` | 4 days |
| `JOURNAL_ENTRY_UPDATE_INACTIVE` | 14 days |

These control how often active/possible and inactive Journal Entries update.

Use only as a script-frequency comparison knob. Increasing the interval may improve performance by doing less work and is therefore not equivalent to an engine optimization.

## Trade-potential refresh

`NON_TRADE_CENTER_STATE_TRADE_POTENTIAL_UPDATE_FREQUENCY = 30`

The shipped comment explicitly states that lower values provide fresher AI data but hurt performance.

This is strong evidence that non-Trade-Center state trade-potential evaluation is an intentionally amortized cost.

If future profiling points to trade/AI work, this define can be used as a causal A/B control:

- if changing only this interval materially changes the same hotspot, the hotspot is likely related to this refresh path,
- it still should not become the main optimization unless reduced simulation frequency is acceptable.

## AI goal update budgets

From `00_ai.txt`:

| Define | Vanilla | Meaning |
| --- | ---: | --- |
| `COUNTRY_GOAL_STRATEGIC_UPDATE_COUNT` | 5 | AIs whose protector scores are updated per day |
| `COUNTRY_GOAL_ADJUSTMENT_UPDATE_COUNT` | 50 | AIs whose antagonize/befriend/threat, neighbor/relevance and attitude state is adjusted per day |

These demonstrate that AI work is already distributed over days rather than recomputed globally each day.

If `CTickTask_UpdateAI` or related tasks become top runtime costs, these are useful for understanding workload scaling.

## Government-alternative combinatorics

`MAX_CANDIDATES_TO_COMBINE_FOR_GOVERNMENT_ALTERNATIVES = 8`

The shipped comment explicitly notes that 8 candidates creates `2^8 = 256` possible governments and that higher values affect performance exponentially.

This is a useful example of a data-controlled combinatorial path. It should not be modified merely for speed unless runtime profiling implicates this specific work.

## Autonomous investment cadence

`AUTONOMOUS_INVESTMENT_UPDATE_COUNT_DIVISOR = 500000`

The shipped comments explain that one autonomous-investment update is executed per tick for each this amount of money entering the investment pool, with a minimum of one, and explicitly warn that setting the divisor too low can badly impact performance.

This is a high-value causal control if autonomous investment appears in the measured hot path.

## Autonomous trade failure budget

`AUTONOMOUS_TRADE_WEEKLY_TRADES_FRACTION_USED_FOR_FAILED_TRADE = 0.2`

The shipped comments state that failed trade attempts consume a fraction of weekly trade capacity specifically so large Trade Centers do not repeatedly attempt unproductive trades and consume performance for no gain.

This is evidence that the trade system already contains explicit performance guards.

## Trade Center construction eligibility

The AI define file contains GDP thresholds for constructing Trade Centers and explicitly warns that decreasing them can adversely affect performance:

- `TRADE_CENTER_MINIMUM_GDP_MARKET_CAPITAL = 100000`
- `TRADE_CENTER_MINIMUM_GDP_NON_MARKET_CAPITAL = 500000`
- additional non-coastal, unrecognized and elapsed-years multipliers

This suggests that the number/distribution of Trade Centers is itself an important workload multiplier.

## Pop consolidation

Victoria 3 1.14.5 contains an explicit `pop_consolidation` game rule.

Vanilla default:

`moderate_consolidation`

Available rule levels in the shipped data:

- `no_consolidation`
- `minor_consolidation`
- `moderate_consolidation`
- `aggressive_consolidation`

Related defines include:

| Define | Minor | Moderate | Aggressive | Max internal level |
| --- | ---: | ---: | ---: | ---: |
| `POP_MERGE_MAX_WORKFORCE_*` | 10 | 30 | 50 | 100 |
| `POP_MERGE_MIN_NUM_POPS_SAME_PROFESSION_*` | 5 | 4 | 3 | n/a |
| `WORKFORCE_RATIO_MAX_UNEMPLOYMENT_FACTOR_*` | 2.5 | 2.0 | 1.5 | 1.0 |

Scaling controls:

- `POP_MERGE_START_POPS = 50000`
- `POP_MERGE_MAX_TARGET_POPS = 100000`

The shipped comments explain that Pop Consolidation identifies Pops small enough that their economic/political impact is considered insignificant and merges them into other Pops in the same building/state.

This is important context: Pop-object-count reduction is already a first-party performance mechanism, not merely a community workaround.

For this project, Pop consolidation should be treated as:

- a workload-control variable,
- a baseline metadata field,
- not the primary native optimization target.

The benchmark manifest should therefore record the active Pop Consolidation rule.

## GUI / map update controls

Examples from `00_graphics.txt`:

- `MAP_MARKER_FULL_UPDATE_FREQUENCY = 1.0` seconds — comment: heavy map-marker work only every X seconds
- `ALERTS_FRAMES_BETWEEN_UPDATES = 5`
- `COA_FLAGS_FRAMES_BETWEEN_UPDATES = 30`
- `POWER_BLOC_COLOR_UPDATE_NUM_FRAMES_BETWEEN = 30`
- `REVOLUTION_MAP_OBJECT_UPDATE_PROVINCES_PER_FRAME = 16`
- `REVOLUTION_MAP_OBJECT_UPDATE_MAX_TIME_PER_FRAME = 0.002`
- `DYNAMIC_TERRAIN_LAZY_UPDATE_PROVINCES_PER_FRAME = 16`
- `DYNAMIC_TERRAIN_LAZY_UPDATE_MAX_TIME_PER_FRAME = 0.0012`

These show deliberate frame-budgeting and update amortization in the presentation layer.

If simulation throughput changes strongly with UI/map state, these are candidate explanatory controls for a separate GUI experiment.

## Battle-condition cadence

`BATTLE_CONDITION_MIN_TICKS_BETWEEN_UPDATE_DEFAULT = 40`

Additional probabilistic refresh logic is applied after the minimum tick count.

This is another example of expensive/variable work being spread across ticks rather than executed continuously.

## How to use these controls

The project should use performance-sensitive defines in three narrowly defined ways:

1. **metadata** — record the baseline values/game rule so benchmark runs are comparable,
2. **causal isolation** — temporarily change one control to see whether a measured native/script hotspot moves with it,
3. **optional compatibility preset** — only later, if users explicitly accept changed update cadence or consolidation.

They should not be mixed into the first native benchmark, because doing so would make it harder to determine whether an improvement came from faster code or simply less simulation work.
