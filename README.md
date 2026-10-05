# Vic3-optimazation

Private research project for improving Victoria 3 simulation performance beyond ordinary script/define tuning.

## 最新の引き継ぎ / Resume on another device

[2026-10-05 PC資料の追加保存・主要9処理の解析](docs/superpowers/reports/2026-10-05-pc-evidence-preservation-ja.md)

154,570件のファイル索引、5,647件の設定・ログ・スクリプト、旧CSVとセンサー記録、復元可能な計測セーブを追加しました。現在のゲーム本体で静的対応を再検証し、主要9処理を起点に80個の関数グループを保存しています。最新の資料保存状態はこちらを優先してください。

[2026-10-05 並列実行経路・雇用callbackの追加調査](docs/superpowers/reports/2026-10-05-dispatch-continuation-ja.md)

共通dispatcher候補からrange runner・heuristicへの接続、雇用のCollect/Sort callbackを追加しました。再現recipeと命令境界を照合するcaller検索toolを保存しています。最新の再開状態はこちらを優先してください。

[2026-10-05 添付ビルドによる追加解析・ツール修正](docs/superpowers/reports/2026-10-05-source-backed-continuation-ja.md)

実測上位3処理のcallbackと処理本体候補を追加照合しました。分割関数の復元・測定不足の表示を修正し、旧形式の解析結果にも対応しています。

[2026-10-05 実測・内部処理調査の引き継ぎ](docs/superpowers/reports/2026-10-05-runtime-benchmark-handoff-ja.md)

3か月の実測CSV、解析結果、内部処理の対応表、iPad・別端末からの再開手順を保存しました。診断基準は暫定16スレッド。OSのCPU/待ち記録は未取得で、性能変更は未実施です。

## Current target

- Victoria 3 Windows 1.14.5
- Caligula: `release/1.14.5` / `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- Clausewitz: `caligula/release/1.14.x` / `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`
- `victoria3.exe` SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## Project rule

Do not start by patching Employment or forcing more worker threads. First establish reproducible measurements, use Victoria 3's built-in TickTask/Script/GUI profilers, and identify the actual serial, locking, scheduling, or task-cost bottleneck.

## Repository boundary

This private repository stores original source code, scripts, signatures/hashes, plans, research results, and a deliberately reduced research-input snapshot under `input-data/`.

The research-input snapshot is kept as separate small archives rather than the original ~122 MB combined `Vic3_data.zip`:

- `input-data/jomini.zip`
- `input-data/clausewitz.zip`
- `input-data/game.zip`
- build identifiers under `input-data/build-info/`

The 2026-10-05 PC evidence expansion adds source/control archives, raw benchmark/log/sensor data and a split compressed benchmark save under `input-data/pc-evidence-2026-10-05/`. Its file inventory, hashes, coverage and restoration instructions are recorded in the latest report.

Large or unrelated Victoria 3 binaries/assets remain excluded. Keep this repository private and review the applicable game/license terms before sharing any third-party game data.

See:

- `docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md`
- `docs/superpowers/plans/2026-10-04-native-performance-optimization-implementation.md`
- `research/preliminary-static-analysis.md`
- `research/input-data-manifest.md`

## Initial completion criterion

Phase 1 is complete only when the same heavy save can be benchmarked repeatedly and produces comparable:

- simulation wall-clock throughput
- TickTask timing CSV
- longest-lock data
- TaskThreadCount scaling results
- script/UI profiler results where relevant

No native performance patch is considered justified until that baseline exists.
