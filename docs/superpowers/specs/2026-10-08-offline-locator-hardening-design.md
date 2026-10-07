# Offline locator hardening

Status: implemented and locally verified; fresh GitHub CI has not started.

## Scope

Close an existing B0 locator gap, without implementing a live adapter.
Resolve each of the six call witnesses through the executable's exception
directory and chained unwind metadata, rather than trusting the carried
caller entry RVA. Reuse RuntimeFunctionIndex for chain resolution. Read only
file-backed PE spans, reject malformed/ambiguous exception metadata, and
require the complete five-byte call to belong to the declared root.

On success retain schema version 1 and existing fields, set
`caller_entry_rva_verified` to true, and add reconstructed
`caller_metadata` per caller. This flag proves metadata association only,
not unwind-code semantics, stack correctness, native ABI, hooking or a
source-level function name. Keep `static_only=true`.

Protect directory inputs against an output outside the directory that is a
hard link to its selected executable. Preserve ordinary JSON overwrite
behavior. This is accidental-overwrite protection, not protection against
a concurrent hostile filesystem replacement.

## Constraints

Keep the fixed executable/source hashes, four allowed/two excluded callers,
manifest include, Stage A/B0 C++ core, native loader/DLL, V3PF format and
golden assets unchanged. Do not weaken any native gate, fabricate code 4
causality, or assert performance gains.

## Verification

Hand-built PE fixtures cover direct/chained roots, fragment gaps,
overlaps, missing roots, bad chains and unbacked/truncated directory data.
Re-hash structural mutations to exercise metadata checks rather than the
hash gate. Run the optional test against the supplied exact ZIP, all Python
tests, B0 CTest/runner, and GitHub CI.
