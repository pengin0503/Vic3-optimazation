# TickTask dependency static evidence

Exact 1.14.5 Graph/List roots: `0x28cf820` / `0x28cf5b0`.
No confirmed-static parent/child relationship recovered at this stage.
Direct structural traversal requires both resolved TickTask identities and
instruction evidence of the parent/child object relationship. The classifier
accepts an explicit reviewed dataflow attestation; it does not discover one.
The extractor emits no dependency edge from calls, indirect sites, shared
helpers or co-references. These cannot establish runtime dependencies,
reachability, critical path, lock causality or performance improvement.
Exact-input counts and unresolved evidence are filled by the reproduction recipe.
