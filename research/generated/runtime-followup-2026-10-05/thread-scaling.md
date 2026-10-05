# Victoria 3 TaskThreadCount scaling diagnostics

> Amdahl-style serial fraction is a diagnostic model only. TaskThreadCount does not represent every Victoria 3 thread, and scheduler, lock, memory, and dependency effects violate ideal Amdahl assumptions. Plateau flags are screening hints, not causes. Unknown/insufficient repeatability never establishes a plateau.

## baseline-no-active-mods

| Threads | Median wall (s) | Speedup | Efficiency | Effective serial fraction | Improvement vs previous | Plateau screen |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 37.510 | 1.000x | n/a | n/a | n/a | unknown |
| 12 | 36.670 | 1.023x | n/a | n/a | 2.24% | unknown |
| 16 | 34.640 | 1.083x | n/a | n/a | 5.54% | unknown |

A plateau should trigger WPR/uProf and TickTask dependency/lock analysis; it does not justify forcing additional workers.
