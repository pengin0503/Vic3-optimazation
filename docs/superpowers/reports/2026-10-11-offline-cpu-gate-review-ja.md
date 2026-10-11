# オフラインCPU研究 Phase 2 / 残る実測ゲート

Date: 2026-10-11
Branch: `research/offline-cpu-parallelism-20261011`
Parent spec: [offline CPU research design](../specs/2026-10-11-offline-cpu-research-design.md)
Implementation plan: [synthetic scheduler comparison](../plans/2026-10-11-synthetic-scheduler-comparison.md)
Phase 1 handoff: [TickTask triage and binary spot-check](2026-10-11-offline-cpu-research-handoff-ja.md)

## 実装・実行したもの

- `research/experiments/scheduler_model/compare_schedulers.py`: Python標準ライブラリだけの合成DAGシミュレータ。即時ready queueと仮想global layer barrierを比較。worker数・dispatch overhead・dependency chainを変えられる。
- `research/experiments/scheduler_model/test_compare_schedulers.py`: 11 synthetic tests。validation, missing/duplicate dependency, cycle, work integer, worker count, ready/barrier differences, dispatch overhead, repeatability, CLI fail closed.
- `research/experiments/scheduler_model/example-workload.json`: 4 synthetic tasks, dispatch cost 1 unit, worker count 1/2/4/8/12/16。
- [README](../../../research/experiments/scheduler_model/README.md): モデルの目的、仮定、例示結果、非結論。

Local synthetic tests: Phase 1 7/7、Phase 2 11/11。GitHub上のソースと検証したローカルファイルの Git blob SHA-1 は5ファイルすべて一致。出力を2度生成してbyte-for-byte一致。GitHub Actionsとcomplete repository Python suiteは実行していない（開発中のActions使用量を避けるため／本環境に全checkoutがないため）。

元の `Vic3_data.zip` SHA-256は `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`、抽出した `victoria3.exe` は `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。研究用fixtureはゲームの実仕事量から生成していない。

## Synthetic result (not game data)

`dispatch_cost_units=1`、work units合計14、work-only critical path 8。これらの整数は任意に設定した架空の値であり、ミリ秒やCPU負荷の実測値ではない。

| Workers | Idealized lower bound | Ready queue | Layer barrier |
| ---: | ---: | ---: | ---: |
| 1 | 14 | 18 | 18 |
| 2 | 8 | 9 | 15 |
| 4 | 8 | 9 | 15 |
| 8 | 8 | 9 | 15 |
| 12 | 8 | 9 | 15 |
| 16 | 8 | 9 | 15 |

この例はworker数の増加がmakespan改善につながらない条件の存在を示す **反例模型** にすぎない。Victoria 3が同じDAG、barrier方式、費用、idle率を持つとは主張しない。

## Phase 3: Offline-only Windows diagnostic host — evidence gap

**更新:** Phase 3のオフライン実装、Linux検証、Windows x64 Releaseのnative CTest 10/10は完了。
[診断・回帰テストの実装記録](2026-10-11-offline-native-diagnostics-phase3-ja.md)を参照。
Windowsの証拠は [run 38148690363](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38148690363)。実ゲームattach code 4の解消、正常に有効化されたDLLセッション全体のstop/finalize、observer overheadは未検証。以下の「未実施」はPhase 2時点の記録。

既存 `src/native/` にはWindows synthetic host、loader、V3PF parserと診断手順がある。以前報告された `Attach failed (no retry), code 4` はゲーム内attachについて未解消のまま。

次に進める場合、まず現在の Windows CTest に module owner lookup / address arithmetic / PE and export validation / remote module mismatch / stop timeout / original exactly once の対応テストがあるか調べ、不足分だけ fixture-based regression を追加する。安全な範囲で成功・拒否経路を実機ゲームなしで確認する。Linux単体試験をWindows runtime相当と認めない。

この研究時点では上記 native fixture test の新規追加・Windows CTest実行は **未実施**。未検証であることはPhase 1/2テスト成功と独立に残す。

## Phase 4: Runtime gate — not satisfied

| Evidence | 現在分かっていること | 次に必要なもの |
| --- | --- | --- |
| 8/12/16 task threads | 3回ずつの平均wall time 37.043 / 34.517 / 34.777s | 完全一致run境界、同期Windows OS trace |
| CPU utilization | HWiNFOが34.7% / 39.7% / 45.2%の補助平均 | game区間と同期したper-thread Running/Ready/Waiting |
| Static TickTask graph | 41 decoded function groups, confirmed parent-child edge 0, unresolved records 59 | 依存関係を裏付ける実際のobject dataflow |
| Windows Task 9 profiler | DLL/loader実装と synthetic host testsあり | real game attach, trace pairing, enabled/disabled overhead |
| Employment lookup | Stage A/B0 owned fixturesの契約がある | live table lifetime, worker scope, ABI/unwind, original semantics |
| GPU offload | offline synthetic implementationあり | device/runtime実測とゲームcritical path、効果の検証 |

この段階では **native最適化パッチの対象は0件**。CPU使用率を増やすためにschedulerのlock、barrierや依存関係を外さない。後日、根本原因を実際の同期tracesで確認し、結果の同一性とゲーム進行wall timeの改善を証明してから個別のtoggle可能なpatchへ進む。

## Reproduce

```sh
python -m unittest discover -s tests -p test_triage_ticktask_unresolved.py -v
python -m unittest discover -s research/experiments/scheduler_model -p 'test_*.py' -v
python tools/triage_ticktask_unresolved.py research/generated/ticktask-dependencies-1.14.5.json --output local-data/ticktask-triage.json
python research/experiments/scheduler_model/compare_schedulers.py research/experiments/scheduler_model/example-workload.json --output local-data/synthetic-scheduler-comparison.json
```

Generated output is local, not part of this branch. Do not add game binaries/large raw traces to the research commit. GitHub PR/merge is deferred to avoid triggering Actions before a final integration gate.
