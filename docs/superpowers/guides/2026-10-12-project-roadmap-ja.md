# Vic3-optimazation全体ロードマップ — 外部計測経路更新

Date: 2026-10-12 JST

更新: 2026-10-13 JST。**現在の主経路は[DLLを使わない外部CPU実測](../../guides/vic3-external-cpu-measurement-ja.md)**。12thread、通常B3回・Sampled S3回を準備し、まずB1/S1で収集成立を確認する。[候補の採否](../reports/2026-10-13-external-cpu-candidate-ja.md)に沿って雇用lookup、民間投資、移民を観測する。Loaderの修復、native profiler Phase4、GPU追加研究は今回の実測の前提から外す。外部計測で足りない問いだけを後続観測へ回す。性能patchは0件のまま。

目標はsimulationの意味・決定性・save安定性を保って同じ期間の実時間を短縮すること。CPU使用率自体は成功条件ではない。現時点の選定/実装性能patchは0件。

## 現在地

- 全体benchmark/static/OS/profiler基盤、Employment Stage A/B0、locator hardeningは実装済み。
- 別区分のoffline CPU Phase1〜4と限定closeoutは完了。全体Phase4/Task9の実ゲームacceptanceは未達。
- 2026-10-12にCPU研究・GPU v2などをPR #16で`main`へ統合し、README全15件の日本語化も完了。以前の「mainへのmerge禁止」「GPU PR15 open」はこの文書の旧記述であり、現在の状態ではない。
- 最終reviewでH2Dの「合計がpositiveでも個別copyはzero」の誤validityを修正し、統合した研究成果へ反映。関連した既存CI成功は合成/オフライン検証であり、実GPUでの計測原因が解決したという意味ではない。
- [2026-10-12 実ゲーム新証拠](../reports/2026-10-12-game-attach-steam-overlay-byte-mismatch-ja.md): disabled attachは`byte_mismatch` / exit8のまま未成功。**別PID**の読取で`LoadLibraryW → MEM_PRIVATE → Steam gameoverlayrenderer64.dll`を確認した。[Issue #17](https://github.com/pengin0503/Vic3-optimazation/issues/17)で、Overlay OFF申告下の新規PID16352でも`byte_mismatch`で拒否され、別PID9280のread-only検証でSteam DLLへのジャンプを再確認した。Phase 4 gateはblocked。
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

現在の順序は、(1)12threadのB1/S1を実測して収集成立を確認、(2)残り4回でcollector負荷と候補の再現性を確認、(3)同run CSV/OS/caller stackから改善対象を選ぶ、(4)不足する内部ABI・寿命・待ち等の問いを限定して調べる、(5)同等性と安全な適用方法を示す個別patch設計・実装、(6)実時間A/Bと長時間save/reloadを検証する。外部調査の開始にnative profilerの成功は要求しない。warm-upを本測定に混ぜない。

最初のユーザー作業は[外部CPU実測ガイド](../../guides/vic3-external-cpu-measurement-ja.md)のB1/S1。旧[disabled接続first-pass](2026-10-12-user-game-validation-first-pass-ja.md)はnative profiler専用の独立経路として保持する。そこにある接続成功前の本反復禁止はnative profilerの比較へ適用し、外部WPR調査を止める条件にはしない。

初期hashだけでsave安定性を認定せず、旧12_r2の余分なframeをtrimしてwall timeを補正したことにもしない。現在の外部実測は[外部CPU実測ガイド](../../guides/vic3-external-cpu-measurement-ja.md)に従う。[Phase4 handoff](2026-10-12-phase4-runtime-evidence-handoff-ja.md)はnative profiler専用の比較・acceptanceに適用する。

## Employmentの独立gate

Stage Aのimmutable owned fixtureとB0のopaque result/original exactly onceは完了。Stage B native shadowはABI、4caller scope、worker寿命、relocation/unwind、table不変性・借用期間、実observer費用が揃うまでOff。元検索を省略するmodeは未承認・未実装であり、shadow一致だけでlookup bypassへ移行しない。

## 非ゲームcloseoutの完了境界

[記録](../reports/2026-10-12-offline-closeout-ja.md): structured parser diagnostics、40/40 indirect context witnesses、GPU lifecycle oracle/transfer model、PR15 sourceレビューとbranch-only consolidationを保存。任意の無制限な全面decompileや同じCI反復は行わない。

今後も限定offline修正は可能だが、主要な残gateは実ゲーム証拠。実GPUのH2D event原因切り分け・GPU常駐multi-stage実装/性能も別のhardware依存研究として残る。このロードマップは、それらを完了したと扱わず、追加性能patchの許可も与えない。

根拠: [全体設計](../specs/2026-10-04-native-performance-optimization-design.md)、[closeout限定設計](../specs/2026-10-12-offline-closeout-design.md)、[CPU gate記録](../reports/2026-10-12-cpu-runtime-evidence-gate-ja.md)、[Employment shadow設計](../specs/2026-10-07-employment-lookup-reuse-shadow-design.md)、[GPU3-session分析](https://github.com/pengin0503/Vic3-optimazation/issues/12#issuecomment-6058076356)。
