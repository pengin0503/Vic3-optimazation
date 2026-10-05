# Offline quality/profiler continuation — 2026-10-05

Repository: `pengin0503/Vic3-optimazation`  
Base main: `39778412637cad6f324960c0b6db07b263daf339`  
Work branch: `work/offline-quality-profiler-spec`  
PR: #8

## 今回の開始時点

最新mainでは、2026-10-05のPC資料保存が既に入っていた。

確認済みの主な状態:

- 13個のTickTaskキャプチャ
- 10個のHWiNFOセンサー記録
- 復元可能な1911.3.1.6のベンチマークセーブ
- 主要9 TickTaskを起点にしたbounded shallow call graph
- 現在の1.14.5実行ファイルで18個のexact-build signatureを再検証
- 既存68 unit/integration testsが保存時点で成功
- native hook / DLL injection / scheduler override / gameplay modificationは未実施

会話添付の `Vic3_data.zip` も再確認した。

- SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`
- Git LFSに保存された `input-data/Vic3_data.zip` のobject SHA-256と一致
- ZIP内に `victoria3.exe` と `victoria3_win_console.exe` を確認

## 今回進めた作業

### 1. Benchmark quality checker

追加:

- `tools/check_benchmark_quality.py`
- `tests/test_check_benchmark_quality.py`

目的は、性能差を読む前にrun setそのものの整合性を自動検査すること。

現在検出する項目:

- duplicate run ID
- expected matrixに対するmissing run
- matrixと異なるTaskThreadCount
- repeat / warmup属性の不一致
- warm-upがmeasured repeat番号を占有する誤設定
- executable/build hash不一致
- save hash不一致
- Pop Consolidation不一致
- TickTask CSV欠落
- TickTask CSV SHA-256不一致
- 3回未満のrepeat
- wall-clock CV過大
- medianから大きく外れたwall-clock outlier

整合性エラーと性能判断上の警告は分離した。

- `valid`: ファイル/条件のintegrity
- `valid_for_performance_claim`: repeatability/outlierも含めて性能主張に進めるか

単発測定を「CV=0で安定」と扱わない既存方針を維持する。

### 2. TDD

production codeを書く前に6件のtestを作成し、実装ファイルが存在しない状態でREDを確認した。

その後、最小実装を追加しローカルscratchで6/6 GREENを確認した。

GitHub側ではPR #8でrepository全体のActionsを実行している。

### 3. Read-only profiler telemetry設計

追加:

- `research/native-profiler-event-format.md`

固定した主な設計:

- exact executable hash + signature/section/RTTI validation
- unsupported buildはzero hooksでfail closed
- QPC timestamp
- Windows thread ID
- stable `target_id`
- per-thread sequence
- FunctionBegin / FunctionEnd
- SchedulerDecision
- WaitBegin / WaitEnd
- Counter
- preallocated per-thread ring buffer
- hot path allocationなし
- hot path file I/Oなし
- hot path mutexなし
- background flush
- dropped-eventを必ず可視化
- cross-thread total orderingを捏造しない
- broken begin/endやsequence gapをparser側で隠さない

SchedulerDecisionは、hook内で統計計算を増やさず、元関数ですでに利用可能な値だけを記録する方針にした。

現在静的に分かっている `MaybeRunRangeExecutionParallelWithHeuristic` 周辺のRVAは研究用の1.14.5 anchorとしてのみ扱い、stable APIにはしない。

## 今回やらなかったこと

証拠ゲートを満たしていないため、以下はまだ行っていない。

- game function detour
- DLL injection/attach
- scheduler return override
- forced chunk count
- worker count override
- Employment parallelization
- lock removal
- simulation state write
- native performance patch

## 現時点のruntime evidence

最新の同一3か月区間の保存済み測定:

| TaskThreadCount | wall-clock |
| ---: | ---: |
| 8 | 37.51 s |
| 12 | 36.67 s |
| 16 | 34.64 s |

各1 observationなので、16 threadsが最速だった事実は記録できるが、差がnoiseより大きいとはまだ証明できない。

HWiNFO記録は旧キャプチャ全体の温度/電力/CPU情報を保存しているが、3か月benchmark区間と厳密同期したOS wait/stack evidenceではない。

したがって、

- 「CPU使用率が低い」
- 「active core平均が少ない」
- 「16 threadsでも全コアを使っていない」

だけからscheduler/lock/dependencyを原因と断定しない。

## 次のEvidence Gate

最短で価値が高い順序:

1. 同じ3か月区間で8/12/16 threadsを各あと2回測定して、各条件3 observationsにする
2. `check_benchmark_quality.py` でrun setを検査
3. `analyze_benchmarks.py` と `analyze_thread_scaling.py` を再実行
4. 16-thread repeatのうち1回でWPR/WPAまたはAMD uProfを同一区間に同期
5. per-thread CPU / wait / context switch / sampling stackをTickTask CSVとcorrelate
6. その結果でserial compute / dependency-barrier / lock / scheduler / memoryのどれが支配的か分類
7. top 1–3 targetだけPhase 4 read-only instrumentationへ進める

完全な1/2/4/6/8/12/16全再測定を待たなくても、上記で現在の8–16 thread領域のrepeatabilityとOS-level原因分離を先に進められる。

## ユーザー側で保存するもの

各測定runごとに最低限:

- wall-clock seconds
- `ticktask_timings.csv`
- TaskThreadCount
- start/end date
- executable SHA-256
- save SHA-256
- Pop Consolidation
- mod/DLC状態
- warm-upかmeasured runか
- OS traceを取ったrunではそのtrace/exportと開始終了対応

CPU使用率や温度も保存価値はあるが、原因分類ではWPR/uProfのwait/stack evidenceを優先する。

## 次のユーザー操作

まず同じセーブ・同じ3か月区間・同じ設定で:

- TaskThreadCount 8: 2回追加
- TaskThreadCount 12: 2回追加
- TaskThreadCount 16: 2回追加

を行う。

可能なら16-threadの追加runの1つでWPR/WPAまたはAMD uProfを同時取得する。

これが揃えば、次回はこちらでquality check → scaling/noise再評価 → OS wait/stack correlation → read-only profilerの最初の具体target選定まで進められる。
