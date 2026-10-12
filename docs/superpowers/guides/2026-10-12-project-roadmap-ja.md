# Vic3-optimazation全体ロードマップ — closeout更新

Date: 2026-10-12 JST

目標はsimulationの意味・決定性・save安定性を保って同じ期間の実時間を短縮すること。CPU使用率自体は成功条件ではない。現時点の選定/実装性能patchは0件。

## 現在地

- 全体benchmark/static/OS/profiler基盤、Employment Stage A/B0、locator hardeningは実装済み。
- 別区分のoffline CPU Phase1〜4と限定closeoutは完了。全体Phase4/Task9の実ゲームacceptanceは未達。
- CPU研究とGPU v2 sourceを `research/offline-cpu-parallelism-20261011` へ統合した。mainへのmerge禁止を維持。GPU PR15はopen。
- 最終reviewでH2Dの「合計がpositiveでも個別copyはzero」の誤validityを修正し、CPU研究とPR15両方へ反映。最終PR pushの既存2workflowはsuccess。実GPUでの計測原因が解決したという意味ではない。
- latest保存済みGPU3-session分析では8-thread Numba CPUが96/96比較でGPUを上回った。新しいresident lifecycleモデルはbytesのみで、GPU高速化を示していない。

## 本体Phaseと次段階

| 全体Phase / Task | 状態 | 次へ進む条件 |
| --- | --- | --- |
| Phase1 / Task1〜5: benchmark | 基盤完了、旧repeatsあり | 現在runのidentity・完全一致CSV・反復条件 |
| Phase2 / Task6: OS相関 | 準備済み、旧sampleあり | 同期区間・clock・Running/Ready/WaitingとCSVの対応 |
| Phase3 / Task7〜8: native mapping | exact static anchors、indirect witnessesあり | 実critical path・worker・動的calleeの確認 |
| Phase4 / Task9: read-only profiler | 実装・Windows synthetic検証済み | 実game attach/code4原因、成功stop、native/CSV相関とoverhead |
| Phase5 / Task10〜11: safe patch | patch0、着手条件未達 | 根本原因・semantic proof・ノイズを超える実時間改善 |
| Phase6 / Task12: scheduler | syntheticモデルのみ | schedulerが主要因と確認した場合に限る追加設計・決定性検証 |

順序は、(1)最新版diagnostic Loaderで実game接続を確認、(2)12/16 × disabled/enabled ×各3回以上の最低12 measured runsをfresh process・交互順序で採取、(3)同期CSV/native/OSから計算・メモリ・待ち・dispatchを分類、(4)対象を1〜3へ限定、(5)read-only shadow/元結果の同等性検証、(6)別設計の小さなtoggleable patchをA/B検証する。warm-upを本測定に混ぜない。

最初のユーザー作業は[disabled接続のfirst-pass手順](2026-10-12-user-game-validation-first-pass-ja.md)のAだけ。Windows artifactの入手先、2binaryのhash、選択PID・初期identity、attach/stop/trace、送付packetを記載した。A/B成功前に本反復を始めない。

初期hashだけでsave安定性を認定せず、旧12_r2の余分なframeをtrimしてwall timeを補正したことにもしない。実測は[Phase4 handoff](2026-10-12-phase4-runtime-evidence-handoff-ja.md)に従う。

## Employmentの独立gate

Stage Aのimmutable owned fixtureとB0のopaque result/original exactly onceは完了。Stage B native shadowはABI、4caller scope、worker寿命、relocation/unwind、table不変性・借用期間、実observer費用が揃うまでOff。元検索を省略するmodeは未承認・未実装であり、shadow一致だけでlookup bypassへ移行しない。

## 非ゲームcloseoutの完了境界

[記録](../reports/2026-10-12-offline-closeout-ja.md): structured parser diagnostics、40/40 indirect context witnesses、GPU lifecycle oracle/transfer model、PR15 sourceレビューとbranch-only consolidationを保存。任意の無制限な全面decompileや同じCI反復は行わない。

今後も限定offline修正は可能だが、主要な残gateは実ゲーム証拠。実GPUのH2D event原因切り分け・GPU常駐multi-stage実装/性能も別のhardware依存研究として残る。このロードマップは、それらを完了したと扱わず、追加性能patchの許可も与えない。

根拠: [全体設計](../specs/2026-10-04-native-performance-optimization-design.md)、[closeout限定設計](../specs/2026-10-12-offline-closeout-design.md)、[CPU gate記録](../reports/2026-10-12-cpu-runtime-evidence-gate-ja.md)、[Employment shadow設計](../specs/2026-10-07-employment-lookup-reuse-shadow-design.md)、[GPU3-session分析](https://github.com/pengin0503/Vic3-optimazation/issues/12#issuecomment-6058076356)。
