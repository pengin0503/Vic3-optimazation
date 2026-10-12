# Resident lifecycle probe — model only

This reuses the existing owned nonnegative int32 `pop_growth` fixture and CPU reference. It does not execute OpenCL, measure GPU time, or implement game formulas. `gpu_executed=false`; time, bandwidth and speedup are null. PR15 and the user's three hardware sessions remain a separate actual GPU experiment.

The bounded question is whether a **fixed-input recurrence whose consumer needs only the final result** can eliminate modeled per-stage host transfers. The independent Python-integer oracle tests cover 0/1/17 records, all four scenarios, stages1/4/32, exact final hashes, shape/dtype/negative input rejection and input nonmutation.

```sh
python resident_lifecycle_probe.py --sizes 0 17 1000000 --stages 1 4 16
python -m unittest discover -p test_resident_lifecycle_probe.py -v
```

The fixed-seed saved matrix has36 cases. For1,000,000 records, uploading all three int32 arrays and downloading each output costs a modeled16/64/256 MB at1/4/16 stages. One-upload/final-only readback costs16 MB. These are decimal byte counts, **not throughput, time savings, or a game speedup**. The per-stage baseline is explicitly one transfer pattern, not a lower bound on all unbatched implementations.

`probe(case, stages, host_updates=True)` disallows batching because updated inputs/lifecycle are unknown. `intermediate_outputs=True` disallows the final-only route: a consumer still needs each intermediate output. Fixed inputs can nevertheless stay resident while outputs are observed: modeled12N+4NS bytes, whereN=records,S=stages. The model does not assume every host observation requires reuploading fixed inputs.

The final digest always describes the fixed-input CPU recurrence; it is **not** the output of unspecified host updates. Flags assess route eligibility, not invented update semantics. An empty fixture measures no GPU execution; zero modeled bytes do not imply zero runtime overhead.

Actual implementation would need ping-pong device state, correct kernel ordering, bounded integer arithmetic, transfer/event/error validation, fair CPU baselines, input update and output consumer ownership, and real repeated hardware measurements. No such timing is available here. Existing v2 hardware results still favor8-thread Numba CPU in96/96 matched comparisons; do not infer that a resident pipeline overturns that finding.
