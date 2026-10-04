# Victoria 3 1.14.5 実測データ取得手順

Date: 2026-10-05
Repository: pengin0503/Vic3-optimazation
Target: Victoria 3 Windows 1.14.5

## 目的

CPU総使用率ではなく、同じゲーム内期間を処理するwall-clock timeとTickTask timingを比較し、serial compute / lock / dependency / scheduler / memory / script / GUIのどれが律速かを絞る。

## 1. ベンチマーク用セーブ

Speed 5で明確に重いlate-gameセーブを1つ選ぶ。

固定するもの:
- セーブ
- DLC
- MOD構成
- Pop Consolidation
- プレイ国
- カメラ位置とzoom
- map mode
- UI panel状態
- graphics
- resolution
- VSync / frame cap
- Windows電源プラン
- BIOS/PBO/COなどCPU設定

セーブのSHA-256取得例:

    Get-FileHash "C:\path\to\heavy-save.v3" -Algorithm SHA256

## 2. 固定ゲーム期間を決める

推奨:
- 開始: 1900-01-01
- 終了: 1901-01-01
- Speed: 5

1年が長すぎれば6か月でもよい。

主ベンチマークでは「実時間60秒」のような固定実時間方式は使わない。処理するゲーム量がrunごとに変わるため。

## 2.5. consoleを使うためdebug modeで起動する

通常起動ではVictoria 3の開発者consoleは使えない前提で進める。

benchmarkで `Threading.TaskThreadCount`、`clear_ticktask_timings`、`dump_ticktask_timings` を使うrunは、起動前にdebug modeを有効化する。

推奨方法:

### Paradox Launcher

LauncherのGame Settingsから **Open game in Debug Mode** を使う。

### Steam launch option

Steam:
1. Victoria 3を右クリック
2. Properties
3. Launch Options
4. 次を設定

    -debug_mode

その状態でゲームを起動する。

consoleはdebug mode起動後にバッククォート/チルダ系キーで開く。キーボード配列によってキー位置が異なる場合がある。

console-enabler MODはbaselineに使わない。MODが追加のscript/UI処理を持つ可能性があり、測定条件を増やすため。

### debug mode自体のoverhead

primary TickTask matrixは全runを同じdebug mode条件で実施する。

ただしdebug modeは通常起動と完全に同一条件とは限らないため、最終的には同じheavy save・同じ固定期間で:

- normal launch
- debug mode launch

のwall-clock controlを最低3回ずつ取り、debug mode overheadを確認する。

TickTask CSVを取得する本計測はdebug modeで統一し、normal launch controlはprofilerなしの純粋なwall-clock比較用とする。

## 3. run matrixを作成

完全セット:

    python tools/prepare_benchmark_matrix.py benchmarks/runs ^
      --threads 1,2,4,6,8,12,16 ^
      --repeats 3 ^
      --start-date 1900-01-01 ^
      --end-date 1901-01-01 ^
      --save-filename heavy-save.v3 ^
      --save-sha256 <SAVE_SHA256> ^
      --country <COUNTRY_TAG> ^
      --pop-consolidation moderate_consolidation

PowerShellでは ^ ではなくバッククォートまたは1行で実行してよい。

標準:
- TaskThreadCount 1 / 2 / 4 / 6 / 8 / 12 / 16
- 各設定 warm-up 1回
- 各設定 measured 3回
- 合計28run

### 最初のquick pass

最初は次だけでもよい:
- 1
- 4
- 8
- 16

各1回 + 必要ならwarm-up。

目的はCSV取得手順と大まかなscaling確認。

## 4. 1 run の実行手順

例: TaskThreadCount = 8

1. 同じheavy saveをload
2. pause
3. consoleで設定

    Threading.TaskThreadCount 8

4. consoleが値を受け付けたことを確認
5. camera/UIを固定状態へ戻す
6. timingをreset

    clear_ticktask_timings

7. Speed 5でunpauseすると同時にstopwatch開始
8. 固定終了日に到達したら即pause
9. wall-clock secondsを記録
10. TickTask timingをdump

    dump_ticktask_timings

11. 出力された ticktask_timings.csv をそのrun directoryへコピー
12. runをfinalize

    python tools/finalize_benchmark_run.py benchmarks/runs/vanilla-t08-r01 --wall-clock-seconds 123.456

finalizerは:
- CSV存在
- frame
- task
- milliseconds
- calls
- longest_lock
- row count
- SHA-256
- byte size

を検証し、完成したrunだけmanifest.jsonを作る。

## 5. ticktask_timings.csv が見つからない場合

1.14.5静的解析ではデフォルトfilename ticktask_timings.csv が確認されている。

まずDocuments側を検索:

    Get-ChildItem "$env:USERPROFILE\Documents\Paradox Interactive\Victoria 3" -Recurse -Filter ticktask_timings.csv -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 10 FullName,LastWriteTime,Length

見つからなければVictoria 3 install directory側も同様に検索する。

最初のrunで実際のoutput pathを記録する。

## 6. 完全matrix

| TaskThreadCount | Warm-up | Measured |
| ---: | ---: | ---: |
| 1 | 1 | 3 |
| 2 | 1 | 3 |
| 4 | 1 | 3 |
| 6 | 1 | 3 |
| 8 | 1 | 3 |
| 12 | 1 | 3 |
| 16 | 1 | 3 |

差が小さい場合はmeasuredを5回程度へ増やす。

CVが3%を大きく超える場合はbackground load、thermal drift、UI条件差などを疑う。

## 7. 解析

TickTask集計:

    python tools/analyze_benchmarks.py benchmarks/runs --json benchmarks/report.json --markdown benchmarks/report.md

Thread scaling:

    python tools/analyze_thread_scaling.py benchmarks/report.json --json benchmarks/scaling.json --markdown benchmarks/scaling.md

Runtime hotspotをnative anchorへ対応付け:

    python tools/triage_benchmark_targets.py benchmarks/report.json <ticktask-rtti.json> --threads 8 --json benchmarks/native-targets.json --markdown benchmarks/native-targets.md

## 8. ChatGPTへ戻す最低限のデータ

推奨:
- benchmarks/report.json
- benchmarks/report.md
- benchmarks/scaling.json
- benchmarks/scaling.md
- 各runのmanifest.json
- 各runのticktask_timings.csv

最も簡単なのはbenchmarks/runsをZIP化して添付すること。

## 9. Script Profiler

primary throughput matrixとは別runで実行する。

確認済みinterface:
- Script.Profiling.Start
- Script.Profiling.Stop
- Script.Profiling.Restart
- Script.Profiling.Gui
- ScriptProfiling.Dump

静的解析で確認したoutput:
- logs/script_profiling.txt

Profiler overheadを混ぜないためprimary matrixと同時に動かさない。

## 10. GUI Data Profiler

比較:
A. map view + 大型panelなし
B. benchmarkで使ったUI状態

注目:
- Only Script
- Self

Only Scriptが大きい:
GUI script解決を疑う。

Selfが大きい:
widget/property/data-binding量を疑う。

## 11. OS-level profile

TaskThreadCount matrix後、代表設定で:
- WPR/WPA
- AMD uProf

取得対象:
- per-thread CPU
- context switch
- wait
- synchronization
- CPU sample stack
- worker idle
- memory/cache stall

これでserial compute / lock / barrier / scheduler / memoryを分離する。

## 12. quick passの解釈

1 -> 遅い
4 -> 大幅改善
8 -> 改善
16 -> ほぼ同じ

なら8付近からserial/dependency/lock/memory側へ移行している可能性が高い。

1 -> 4 -> 8 -> 16 と継続改善するならscheduler/worker scalingをさらに調べる価値がある。

1 -> 4で少しだけ改善し8/16でほぼ変わらないなら強いserial bottleneck、lock、memory stall、dependency chainを優先する。

## 13. baseline前に行わないこと

- Employmentを強制並列化
- Scheduler heuristicを常時parallel化
- TaskThreadCount増加だけを最適化と判断
- Pop/Culture削減をbaselineへ混ぜる
- runごとにUI条件を変える
- profilerを全部同時に有効化

## 14. Phase 1完了条件

揃えるもの:
- top TickTasks
- longest_lock上位
- 1から16までのthread scaling
- run variance
- Script/GUI contribution
- 少なくとも1つのOS-level trace

これが揃えば、既に静的解析済みの258 TickTask native anchorsから上位1〜3個を選び、read-only native profilerへ進める。
