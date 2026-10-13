# 外部CPU計測を主経路にする設計

日付: 2026-10-13 JST。基準main: `e738fa52c25760d57479d7ff7304f4209882d387`。

## 目的と承認範囲

ユーザーの「ではその作業を進めて、あとは実測のみにして」に基づき、前の提案①を実測可能な状態まで進める。文化・人口・国数・更新頻度・処理順序を変えず、同じゲーム期間の実時間を短縮する目標を維持する。今回は既存ツールを使う調査経路・入力ひな形・操作手順を完成させる。新しい収集器、一般的な受け入れゲート、合成スケジューラー、GPUモデル、性能パッチは作らない。

この変更の完成は「次に必要なのがWindows上の実測」という意味。実測後には分析、候補の採否、必要なら個別パッチの設計・実装が残る。「プロジェクト全体が実測だけで完成する」「パッチの準備が済んだ」とは扱わない。

## 既存設計からの変更

- WPR/WPAとゲーム組み込みTickTask CSVを候補選定の主経路にする。Issue #17とnative profiler Phase4の成功はこの外部調査の前提条件にしない。
- `tools/check_cpu_runtime_gate.py`、`research/phase4/`、Loaderの安全性検査は変更しない。旧Phase4がblockedでも外部調査は進められるが、blockedをpassedに書き換えない。
- 外部計測で説明できない具体的な問いが残る場合だけ、その問いに必要な追加観測を設計する。外部サンプリングだけで内部ABI・container寿命・並行アクセスの安全性を証明したことにしない。
- パッチのbuild検証、同等性、安定性、実時間A/B条件は維持する。必要な証拠を自作DLLに限定することはしないが、適用方法を未解決のまま実行時パッチを投入しない。

## 調査対象

最初の改善案は、既存Stage A/B0に接続する**雇用の正の検索slotの検証付き再利用**。これは調査上の第一候補であり、性能上の最優先対象や実装許可ではない。民間投資・経済移民の共有helperも同時に観測し、雇用関連lookupの費用が小さければ採用を保留する。

同じitemの4つの静的検索siteが毎回実行されるか、配列・tableが同一か、call間で変化しないかは不明。全件resetを保ち、ループ融合、生pointerキャッシュ、TLS buffer持続化は今回の変更対象にしない。

## 最初の実測セット

Victoria 3 Windows 1.14.5、TaskThreadCount=12、同saveの1911-03-01→1911-06-01。speed、MOD、DLC、UI、camera、rules、host条件を実機で確認し固定する。12は旧比較の診断基準であり、全PCの最適値ではない。

通常実行Bを3回、既存`Vic3Sampled`によるCPUサンプリングSを3回。順序はB1,S1,S2,B2,B3,S3。開始前にB/Sそれぞれでwarm-upし、毎回同saveをreloadする。通常は同一game processを使い、再起動が必要なら新batchとして扱う。旧9回の値を新batchへ混ぜない。

新batchにはcollectorなしとありの**別variant**を使う。比較はobserver overheadの参考であり、性能パッチのspeedupではない。CSVのframe/task/calls一致と、build/save/設定の同一性を確認する。ばらつきや境界差があればそのrunだけ再取得し、丸ごとの無条件再収集はしない。

初回はS1までで収集・停止・CSVの整合性を確認する。失敗時は残り4回を実行しない。Schedulingはsampledと同時収集せず、待ち/dispatchの問いが残る場合に別runで行う。

## 再利用する部品

- `research/vic3-focused-cpu.wprp`: 既存のSampled/Scheduling分離profile。
- `tools/prepare_benchmark_matrix.py` / `finalize_benchmark_run.py`: 未測定templateと実測後CSV hash。
- `tools/check_benchmark_quality.py` / `analyze_benchmarks.py`: workload境界とvariant別集計。
- `tools/normalize_os_profile.py` / `correlate_os_profile.py`: 実exportのheader・unit・PID/ASLRを確認した後の照合。
- `research/generated/os-capture-preparation-2026-10-05/native-region-catalog.json`: 42範囲の既存照合表。
- `research/external-cpu/employment-lookup-catalog.json`: 上記にないlookup/fallbackの2つの限定excerpt。保存済み雇用証拠から既存builderで作り、同じOS入力へ別々に照合する。

## 完成条件

6件の未測定template、実行順matrix、日本語操作手順、候補の採否基準、既存証拠の限界が保存されている。添付ZIP/exeと選択した既存range hashを照合し、既存解析経路を合成入力で確認する。新しい実機結果・速度・観測負荷はすべて未測定。Windowsの開始/停止と実exportはユーザーの実測で確認する。
