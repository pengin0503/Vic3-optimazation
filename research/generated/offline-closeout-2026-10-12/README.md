# Bounded offline closeout witnesses

`indirect-witnesses.json` follows exactly the existing 40 unresolved indirect instruction RVAs, using Capstone 5.0.7 and the exact 1.14.5 executable. Both generations were byte-identical; owned decoder tests passed 8/8. Source JSON/executable hashes and per-range byte digests are recorded in the JSON. It contains 27 memory calls, 3 memory jumps, 2 register calls and 8 register jumps. Every callee remains unknown; confirmed dependency edges remain zero.

Reproduce from repository root:

```sh
mkdir -p local-data
python tools/witness_ticktask_indirect_sites.py input-data/Vic3_data.zip research/generated/ticktask-dependencies-1.14.5.json > local-data/indirect-witnesses.json
```

The tool writes stdout only. Choose a new output file; shell redirection is not input-alias protection. It decodes each file-backed declared range from its beginning, rejects partial ranges and non-boundary/non-indirect sites, and retains at most eight preceding instructions. Source ownership is reused from the existing static evidence, not newly authenticated as a complete source-level function.

At `0x7d670f`, `RAX <- [RCX]`, `RDX << 2`, `R8D=4`, then `call [RAX+8]` support a buffer/allocator-style indirect interface. At `0x64b336` and `0x3c2d720`, `call [RAX+0x10]` remains consistent with prior container cleanup hypotheses. These are not resolved allocator identities, graph-object dataflow, parent/child edges, actual execution cost or performance improvements. The exact instruction operands are witnesses; interpreting the object/interface requires separate evidence.

The bounded question is complete: all current indirect RVAs have reproducible instruction/context witnesses. Unlimited graph expansion and new native behavior are not part of this result.
