# Victoria 3 TaskThreadCount scaling diagnostics

> Amdahl-style serial fraction is a diagnostic model only. TaskThreadCount does not represent every Victoria 3 thread, and scheduler, lock, memory, and dependency effects violate ideal Amdahl assumptions. Plateau flags are screening hints, not causes. Unknown/insufficient repeatability never establishes a plateau.

## user-3month-repeat-batch

| Threads | Median wall (s) | Speedup | Efficiency | Effective serial fraction | Improvement vs previous | Plateau screen |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 36.880 | 1.000x | n/a | n/a | n/a | unknown |
| 12 | 34.530 | 1.068x | n/a | n/a | 6.37% | no |
| 16 | 34.660 | 1.064x | n/a | n/a | -0.38% | yes |

First plateau-screen point: **16 task threads**.

A plateau should trigger WPR/uProf and TickTask dependency/lock analysis; it does not justify forcing additional workers.
