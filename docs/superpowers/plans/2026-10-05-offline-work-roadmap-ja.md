# 実測データなしで進められる作業

Date: 2026-10-05
Repository: pengin0503/Vic3-optimazation

## 結論

実測データがなくても作業は継続できる。

ただし、現在は広く逆解析する段階ではなく、実測後にすぐ上位hotspotへ移れる基盤を完成させる段階。

優先順位:
1. runtimeデータ取得を簡単にする
2. runtime hotspotをnative targetへ自動変換する
3. build更新に強いvalidationを完成させる
4. read-only profilerの設計を先に固める
5. 高価値候補のshallow call graphを限定的に深掘りする

性能変更そのものはまだ行わない。

## P0: 今すぐ価値が高い作業

### 1. TickTask dependency graphの静的復元

目的:
- TickTask間のparent/child
- dependency chain
- priority
- execution rate
- task registration structure

を可能な範囲で復元する。

既に使える材料:
- 258 TickTask vtable
- TickTask.Graph
- TickTask.List
- graph job / task scheduler anchors
- task registration周辺のstrings/RTTI

価値:
CPU使用率が低い原因がworker不足ではなく長いdependency chainである可能性を評価しやすくなる。

想定成果物:
- research/ticktask-dependency-static-map.md
- research/generated/ticktask-dependencies-1.14.5.json

### 2. 高価値TickTaskのshallow call graph解析

対象候補:
- UpdateEmployment
- UpdateStatePopNeedCache
- ProcessPopPurchases
- RecalculateModifierNodes
- UpdateWorldMarket
- UpdateAI
- UpdateStateTrades
- UpdatePopGrowth
- MergeSmallPops

調べる範囲:
- tail vfuncから2〜3段のcallee
- range executionへ入るか
- child jobをdispatchするか
- synchronization primitiveへ入るか
- 大きなiteration helperへ入るか

全面decompileはしない。

実測後に上位になったtargetだけ深掘りできる状態を作る。

### 3. Scheduler heuristicのread-only telemetry設計

既に特定済み:
- MaybeRunRangeExecutionParallelWithHeuristic
- 0x7db150–0x7dba91

先に決められるlog field:
- caller / TickTask
- range begin/end
- range length
- TaskThreadCount
- heuristic result
- min
- max
- mean
- variance/stddev
- threshold
- chunk/work count
- thread ID
- QPC timestamp

この段階ではhookしない。

何を観測すればparallel拒否理由を判定できるかだけ固定する。

### 4. Native profiler event format設計

実測なしでも設計可能。

候補event:
- FunctionBegin
- FunctionEnd
- SchedulerDecision
- WaitBegin
- WaitEnd
- Counter

共通header:
- timestamp_qpc
- thread_id
- event_type
- target_id
- sequence

設計原則:
- hot pathでheap allocationしない
- hot pathでfile I/Oしない
- hot pathでmutexを取らない
- per-thread ring buffer
- background flush
- dropped-event counter
- build/hash metadataをfile headerへ保存

### 5. Signature validation強化

現在:
- exact 1.14.5 hash
- exact byte window
- fail-closed validation

さらに可能:
- high-value TickTask tail vfuncのsignature生成
- surrounding code metadata
- section validation
- RTTI/vtable cross-check
- unsupported-build reason code
- signature DB versioning

### 6. Version migration workflow

Victoria 3更新時に:

    new victoria3.exe
      -> analyze_vic3.py
      -> map_ticktask_rtti.py
      -> compare_static_analysis.py
      -> signature regeneration
      -> migration report

を1command化できる。

長期保守に重要。

## P1: 実測なしでも有益な作業

### 7. built-in game timer activation path解析

既に確認:
- Game Date
- Seconds
- gametimer_YYYYMMDD_HHMMSS.tsv
- writer function

残り:
- caller
- console/interface
- enable condition
- output path

使えればmanual stopwatchを減らせる。

### 8. scripted_testsでend-date自動化

retail buildにJomini scripted-test managerあり。

調査:
- loaded saveから開始可能か
- date triggerだけ利用できるか
- failure save I/Oを抑制できるか
- test outputを最小化できるか

runtime採用はoverhead計測後。

### 9. WPR/uProf import parser準備

trace取得はWindowsが必要だが、export後のschema処理は先に作れる。

join対象:
- run_id
- thread CPU time
- wait time
- context switch
- sampling stack
- worker idle
- memory/cache indicators

### 10. Benchmark quality checker

自動検出:
- missing run
- duplicate run ID
- wrong TaskThreadCount
- different save hash
- different build hash
- different Pop Consolidation
- CSV hash mismatch
- outlier
- excessive CV
- warm-upの混入

実測ミス防止に有効。

### 11. Causal A/B experiment generator

performance-sensitive defineを最適化としてではなく原因分離に使う。

例:
- baseline
- trade-potential refreshだけ変更
- Journal Entry cadenceだけ変更
- Pop Consolidationだけ変更

特定TickTask costが追随するか確認する。

## P2: 可能だが実測前にやり過ぎない方がよい作業

### 12. Employment全面逆解析

現在:
- CTickTask_UpdateEmployment
- native tail anchor 0x13b8310

まで分かっている。

Employmentがruntime top hotspotと確認されるまで全面解析は保留。

### 13. Market / AI / Pop全面decompile

同様に保留。

258 TickTaskにnative anchorがあるためruntime ranking後の方が効率的。

### 14. Scheduler behavior変更

静的解析は可能だが変更禁止。

まだ行わない:
- heuristic always true
- threshold変更
- chunk count強制
- worker数だけ増やす

### 15. 実game hook

作ってよい:
- loader/profiler interface
- config
- event schema
- ring buffer
- hash checker
- signature parser
- mock target
- unit test

まだ作らない:
- game function detour
- simulation state write
- scheduler return override
- Employment parallelization
- lock removal

## 推奨offline実行順序

### Offline Phase A
TickTask dependency graph復元。

### Offline Phase B
高価値9候補のshallow call graph。

### Offline Phase C
read-only profiler event / ring-buffer spec。

### Offline Phase D
signature/build manifest強化。

### Offline Phase E
runtime automation準備:
- benchmark quality checker
- game timer activation path
- scripted_tests fixture
- WPR/uProf import schema

## 実測が1回分だけ来ても進められる

完全28runを待つ必要はない。

最初に:
- TaskThreadCount 1
- 4
- 8
- 16

のquick passが来れば:

1. scaling curve仮判定
2. top TickTask ranking
3. longest_lock ranking
4. top TickTask -> RTTI/vtable/native anchor対応
5. 次に完全測定すべきthread count選定
6. WPR/uProf代表設定選定

ができる。

## Evidence Gate

Native performance patch開始前に必要:
1. reproducible heavy-save benchmark
2. TickTask top cost
3. longest_lock
4. TaskThreadCount scaling
5. Script/GUI contribution
6. OS-level wait/CPU evidence
7. top 1〜3 native target mapping

現在、静的target mappingと安全基盤は大幅に前倒し済み。

不足しているのは主にruntime evidence。

## 判断

Windowsなしでもまだ進められる。

最も価値が高いのは:
- dependency graph
- shallow call graph
- profiler event/ring-buffer設計
- validation/update tooling
- benchmark automation

258個すべてを深く解析するより、実測後に即上位targetへ進める準備を完成させる方が効率がよい。
