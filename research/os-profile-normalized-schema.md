# Normalized OS profile v1

Mapping-driven CSV only. No verified WPA/uProf export schema is available yet.
One import has one event type (`cpu_sample`, `wait`, `context_switch`) and run.
Top-level: `format_version=1`, nonempty `run_id`, `source`, `source_filename`,
`source_sha256`, exact recorded `executable_sha256`, `unmapped_columns`, `rows`.
Row: `event_type`, integer `timestamp_ns`, unchanged string `thread_id`,
`source_row` (CSV record index, starting at 2). Optional `process`, `module`,
raw `stack`, hex `module_base` / `instruction_va`, integer `duration_ns`,
`cpu_time_ns`, `wait_time_ns`, nonnegative integer `context_switches`.
A missing optional numeric value stays absent; it is never replaced with zero.
No RVA is invented at import. Addresses are validated uint64 integers internally,
hex strings at the JSON boundary. A VA below its base is rejected.

Mapping requires `executable_sha256`, `event_type`, `timestamp_column`,
`timestamp_unit`, `thread_id_column`. Optional `<field>_column` selects process,
module, module_base, instruction_va, duration, cpu_time, wait_time,
context_switches, stack. Each mapped time field requires `<field>_unit`, one of
`ns`, `us`, `ms`, `s`. Decimal arithmetic rejects sub-nanosecond precision,
negative/nonfinite values; no rounding. `decimal_separator` is explicitly `.`
or `,`; grouping separators are unsupported. `delimiter` and `encoding` can be
specified (defaults comma / utf-8-sig). CSV quoting is preserved by the CSV parser.
All selected columns must exist, including optional mapped columns. Extra columns
are explicitly unmapped by omission from mapping and listed in `unmapped_columns`.
`include_raw_source_row` defaults false. Build and run identity are supplied by the
operator from the run manifest, never inferred from a stack or filename.

## Mapping template — examples only, not verified WPA/uProf column names

Replace placeholders with exact columns from the real export; remove optional
mappings when those columns are absent. All mapped columns must exist.

```json
{
  "executable_sha256": "9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54",
  "event_type": "cpu_sample",
  "timestamp_column": "REPLACE_WITH_TIMESTAMP_COLUMN",
  "timestamp_unit": "s",
  "thread_id_column": "REPLACE_WITH_THREAD_COLUMN",
  "module_column": "REPLACE_WITH_MODULE_COLUMN",
  "module_base_column": "REPLACE_WITH_MODULE_BASE_COLUMN",
  "instruction_va_column": "REPLACE_WITH_INSTRUCTION_VA_COLUMN",
  "stack_column": "REPLACE_WITH_RAW_STACK_COLUMN",
  "delimiter": ",",
  "decimal_separator": "."
}
```

`timestamp_unit=s` above is illustrative, not a vendor default. For waits use
`event_type=wait`, `wait_time_column=REPLACE_WITH_WAIT_COLUMN`, and explicit
`wait_time_unit`. For context switches use `event_type=context_switch` with
`context_switches_column=REPLACE_WITH_COUNT_COLUMN`. CPU time and duration may
likewise be mapped only when their units and meanings are known. Aggregated
counts must not be confused with individual context-switch event rows.

Use the normalize -> catalog -> correlate commands in `os-profiling-plan.md`.
A normalized row requires both a Victoria 3 module and valid VA/base to match.
The correlator separates processes when process identity was mapped and reports
metric observation counts so missing metric cells do not look like zero time.
