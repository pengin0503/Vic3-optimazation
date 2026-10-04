# Runtime automation findings

Date: 2026-10-04
Target: Victoria 3 Windows 1.14.5

## Purpose

This note records runtime and test infrastructure found in the supplied Vic3_data.zip that can reduce manual work during Phase 1. None of these mechanisms is treated as part of the benchmark baseline until it is verified in the real Windows game process.

## Confirmed scripted-test framework

The shipped file game/tools/scripted_tests/scripted_tests.md documents a built-in scripted-test framework.

Confirmed capabilities from the shipped documentation:

- one text file is a test suite
- a suite has a last_date
- each test case can define success and fail triggers
- success is evaluated before fail on the same day
- run_count controls how many pass/fail cycles are counted
- acceptable_fail_rate is metadata only
- scripted tests can be enabled by command-line argument
- in-game console command scripted_tests toggles the system
- save creation around failures can be controlled
- text results are written to the Documents area
- XML results are written to the game binaries area

The executable also contains these related strings:

- scripted_tests
- no_save_after_failed_test
- save_before_failed_test
- acceptable_fail_rate
- last_date
- tests
- tests.txt
- {}_testoutput.xml
- source path cw/jomini/modules/core/source/testmanager.cpp

This is strong evidence that the test manager is shipped in the retail 1.14.5 build.

## Benchmark relevance

The scripted-test system may be useful for a later automation layer because a test can use a date trigger as a deterministic endpoint.

It is not yet used by the primary benchmark for three reasons:

1. behavior when enabling tests on an already-loaded late-game save is not yet runtime verified
2. test result and failure-save I/O may add noise
3. the framework does not itself provide the primary wall-clock metric

The first real benchmark should therefore remain manual at the start/end boundary while using the built-in TickTask timing commands.

After baseline variance is known, scripted tests can be measured as an optional automation aid. If their overhead is negligible, they can be used to reduce human timing error.

## Built-in game timer lead

The executable contains Jomini timer output strings:

- Failed to log timer info to file: {}
- Game Date
- Time Unit
- Seconds
- gametimer_%04d%02d%02d_%02d%02d%02d
- .tsv

The nearby source path is in Jomini core rather than Victoria-specific script data.

This suggests a built-in game timer or integration-test timing path that can write a TSV containing game date and seconds. The trigger/console interface was not identified with enough confidence in the current static pass, so this remains a research lead only.

Do not replace the wall-clock benchmark with this mechanism until the command path and semantics are verified in-game.

## TickTask output behavior

The 1.14.5 executable confirms:

- clear_ticktask_timings discards previously accumulated TickTask timings
- dump_ticktask_timings writes the accumulated data
- default filename string: ticktask_timings.csv
- CSV columns: frame, task, milliseconds, calls, longest_lock
- success/failure strings include Wrote %d rows to %s and Could not write %s
- log_ticktask_performance writes continuous TickTask performance events to profiling.log

The continuous profiling.log mode is useful for investigating isolated slow ticks, but the fixed-interval CSV dump remains the preferred Phase 1 aggregate capture because continuous logging can add I/O overhead.

## Script profiler

Confirmed executable strings:

- Script.Profiling.Gui
- Script.Profiling.Start
- Script.Profiling.Stop
- Script.Profiling.Restart
- ScriptProfiling.Enable
- ScriptProfiling.Dump
- logs/script_profiling.txt

The script profiler should be run as a separate diagnostic pass, not during the primary throughput matrix until its overhead has been measured.

## GUI data profiler

The executable and Jomini GUI data expose a dedicated GUI Data Profiler.

Embedded help text distinguishes:

- Only Script: time spent resolving GUI scripts
- Self: work other than GUI script resolution; high Self suggests widget/property volume is the limiting factor rather than script evaluation itself

This distinction matters because a UI-related simulation slowdown can come from expensive GUI scripts or from the volume of widgets/properties and GameState reads.

## Clausewitz frame/thread profiler

The shipped clausewitz/gui/profiler.gui exposes:

- frame time
- ns per tick
- thread selection
- timer filtering
- recording pause/resume
- current-frame tracking
- PdxProfilerGuiWriteFrameCSV

This profiler can complement TickTask data when a GUI/render/GameState synchronization hypothesis becomes credible.

## Performance-sensitive script/define controls observed

The supplied game/common/defines data contains performance-relevant controls, including:

- JOURNAL_ENTRY_UPDATE_ACTIVE
- JOURNAL_ENTRY_UPDATE_INACTIVE
- NON_TRADE_CENTER_STATE_TRADE_POTENTIAL_UPDATE_FREQUENCY
- COUNTRY_GOAL_STRATEGIC_UPDATE_COUNT
- COUNTRY_GOAL_ADJUSTMENT_UPDATE_COUNT
- MAX_CANDIDATES_TO_COMBINE_FOR_GOVERNMENT_ALTERNATIVES
- POP_MERGE_MAX_WORKFORCE_* families
- POP_MERGE_MIN_NUM_POPS_SAME_PROFESSION_* families
- POP_MERGE_START_POPS
- POP_MERGE_MAX_TARGET_POPS
- MAP_MARKER_FULL_UPDATE_FREQUENCY

Several comments explicitly warn that lower update intervals or larger search spaces hurt performance.

These defines are useful later as controlled comparison knobs or as evidence for where Paradox itself expects cost. They are not the primary goal of this project because the project is intended to preserve simulation richness rather than win performance mainly by doing less simulation.

## Decision

For the next Windows runtime session:

1. use the existing manual fixed-date benchmark first
2. capture ticktask_timings.csv
3. record wall-clock duration
4. complete the TaskThreadCount matrix
5. use script and GUI profilers in separate passes
6. only then measure whether scripted_tests or the Jomini game timer can safely automate the run boundary

No native hook implementation should start before the runtime evidence gate is satisfied.
