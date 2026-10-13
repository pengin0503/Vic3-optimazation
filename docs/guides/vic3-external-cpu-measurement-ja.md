# Victoria 3：DLLを使わない次の実測

2026-10-13 JST。対象はWindows 1.14.5。**次に行うのはB1とS1の2回**。S1の停止・CSV保存まで成功してから残り4回へ進む。Loader/DLLのビルド・接続、Overlay設定変更、GPU計測はこの手順には不要。

目的は改善候補の費用を絞ること。今回B/Sの比較はcollectorの観測負荷であり、ゲームを高速化した結果ではない。CPU使用率の上昇は成功条件にしない。

## 1. 準備

最新mainを含むリポジトリのroot（`tools/`と`research/`があるdirectory）を使う。Python 3.10以降、Windowsの`wpr.exe`、解析用WPAが必要。このpacketのfinalize/quality/analysisには新しいPython packageは不要。WPA/必要ならxperfは[Windows Performance Toolkit](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/)から導入する。

同じ**管理者PowerShell**を開始・marker・status・停止に使う。既存の別WPR記録がある場合は開始しない。別sessionを無条件にcancel/stopしない。今回専用sessionの名前はrun IDごとに変わる。

```powershell
$repoRoot = (Get-Location).Path
if (-not (Test-Path -LiteralPath 'research/external-cpu/matrix.json')) { throw '最新のrepo rootへ移動してください' }
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw '管理者PowerShellで実行してください' }
Get-Command python, wpr -ErrorAction Stop | Select-Object Name, Source
python --version
wpr -profiles research/vic3-focused-cpu.wprp
if ($LASTEXITCODE -ne 0) { throw 'WPR profileを読み込めません。測定を始めないでください' }
wpr -status

$batchRoot = Join-Path $repoRoot 'raw-captures/external-cpu'
if (Test-Path -LiteralPath $batchRoot) { throw '既存batchには上書きしません。保存済みbatchを保持し、別の空batch保存先を指定してください' }
New-Item -ItemType Directory -Path (Join-Path $repoRoot 'raw-captures') -Force | Out-Null
Copy-Item -LiteralPath 'research/external-cpu/run-templates' -Destination $batchRoot -Recurse
Copy-Item -LiteralPath 'research/external-cpu/matrix.json' -Destination (Join-Path $batchRoot 'matrix.json')
```

6件は`manifest.template.json`で、実測値はまだない。rootのmatrixの`directory`が各runの保存先。

事前にgame speed、国、MOD/playset、DLC、Pop consolidation、graphics/resolution、VSync/frame cap、camera/UI、power plan、BIOS/CPU設定を確認して固定する。localの各templateの対応するnullへ**実際の値**を記入する。no MODなら`[]`、不明ならnullを残す。不明なまま「vanillaと同条件」と認定しない。全6件で同じ条件を記録し、`environment.process_launch_state`に同じprocessでreloadする方式を記す。

同saveの1911/3/1→6/1、`Threading.TaskThreadCount 12`。診断基準が12であって、全ユーザー向けの最適値を確定したわけではない。ゲームの自動saveが区間中に入る条件は避け、ゲーム速度とカメラ/UIを固定する。

B（collectorなし）、S（Vic3Sampledあり）それぞれをwarm-upしてから同saveをreloadする。warm-upをこの6件へfinalizeしない。Sのwarm-upも下記の開始/停止を専用の別保存先で行い、必ず停止する。本計測は同game processで同saveを毎回reloadする。再起動・crashや条件変更が必要なら現在batchを保留し、新batchにする。

Bのwarm-upではcollectorなしで同じ3か月を進めてpauseする。Sのwarm-upは同saveをreloadし、12thread/同settingsを確認して開始位置でpauseしてから次を使う。warm-upでも中止時の停止は必要。

```powershell
$warmupFolder = Join-Path $batchRoot 'warmup-sampled'
if (Test-Path -LiteralPath $warmupFolder) { throw 'warm-up保存先は使用済みです。上書きしません' }
New-Item -ItemType Directory -Path $warmupFolder | Out-Null
$warmupSession = 'Vic3-External-Sampled-Warmup'
wpr -start research/vic3-focused-cpu.wprp!Vic3Sampled -filemode -recordtempto $warmupFolder -instancename $warmupSession
if ($LASTEXITCODE -ne 0) { throw 'warm-up WPR開始失敗。状態を確認してください' }
try {
    Read-Host 'gameで同じ3か月を進めてpauseし、この端末へ戻ってEnter' | Out-Null
} finally {
    wpr -stop (Join-Path $warmupFolder 'warmup.etl') -instancename $warmupSession
    $warmupStopExit = $LASTEXITCODE
    wpr -status -instancename $warmupSession
}
if ($warmupStopExit -ne 0) { throw 'warm-up停止失敗。専用sessionを停止してから進んでください' }
```

この後、同saveをreloadして本計測B1へ進む。warm-up保存先にはmanifestを作らず、analysisの本計測へ混ぜない。

| 順 | run ID | 種類 |
| ---: | --- | --- |
| 1 | `ext-baseline-t12-r01` | B、WPRなし |
| 2 | `ext-sampled-t12-r01` | S、Vic3Sampled |
| 3 | `ext-sampled-t12-r02` | S |
| 4 | `ext-baseline-t12-r02` | B |
| 5 | `ext-baseline-t12-r03` | B |
| 6 | `ext-sampled-t12-r03` | S |

## 2. 各runの開始前

ゲームを同saveでloadし、1911/3/1でpauseする。consoleで`Threading.TaskThreadCount 12`の受付を確認し、`clear_ticktask_timings`を実行する。consoleの操作を終え、同camera/UIへ戻す。

以下はB1の例。以降は`$runId`だけを表のIDへ変更する。

```powershell
$runId = 'ext-baseline-t12-r01'
$matrix = Get-Content -LiteralPath (Join-Path $batchRoot 'matrix.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$selected = @($matrix.runs | Where-Object { $_.run_id -eq $runId })
if ($selected.Count -ne 1) { throw 'matrixにあるrun IDを指定してください' }
$runFolder = Join-Path $batchRoot $selected[0].directory
if (Test-Path -LiteralPath (Join-Path $runFolder 'manifest.json')) { throw 'このrunは確定済みです。再使用しません' }
$templatePath = Join-Path $runFolder 'manifest.template.json'
$manifest = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.os_capture.status -ne 'not_started') { throw '開始済みrunは再使用しません。別のrun保存先を用意してください' }
$gameProcesses = @(Get-Process victoria3 -ErrorAction SilentlyContinue)
if ($gameProcesses.Count -ne 1) { throw 'Victoria 3を1つ起動し、開始位置でpauseしてください' }
$gameProcess = $gameProcesses[0]
$exeHash = (Get-FileHash -LiteralPath $gameProcess.Path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($exeHash -ne $manifest.build.victoria3_exe_sha256) { throw 'exeの版が違います。このcatalogは使えません' }
$savePath = Read-Host '今回loadしたsaveの絶対path'
$saveHash = (Get-FileHash -LiteralPath $savePath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
if ($saveHash -ne $manifest.save.sha256) { throw '想定saveと不一致です。今回の固定条件を確認してください' }
$manifest.os_capture.game_pid = $gameProcess.Id
$manifest.os_capture.process_start_utc = $gameProcess.StartTime.ToUniversalTime().ToString('o')
$manifest.os_capture.game_process_path = $gameProcess.Path
$manifest.os_capture.module_base = '0x{0:x}' -f $gameProcess.MainModule.BaseAddress.ToInt64()
$manifest.os_capture.status = 'prepared_live_identity'
$manifest.warmup_performed = $true # 上述のB/S warm-upを実際に行った場合のみ
[IO.File]::WriteAllText($templatePath, ($manifest | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
$captureSession = "Vic3-External-$runId"
```

hash一致だけではloadしたsaveの証明にならないので、実際のload画面・開始日・国も確認する。consoleに実際のCSV出力先が表示される場合はそのpathを使う。ファイル名引数の未検証構文は使わない。

## 3. B：通常実行

WPRを開始しない。pause解除から6/1でpauseするまでの実時間を、同じ計時方法で測る。端末の`Read-Host`、チャット返信、WPR markerの間隔はgameの実時間ではない。

終了後に下記「CSV保存」へ進む。`os_capture.status`は実行終了を確認して`no_collector`にする。BにはETL、lost events、marker時刻を作らない。

## 4. S：CPUサンプリング

2の準備後、まだgameをpauseした状態で実行する。

```powershell
wpr -start research/vic3-focused-cpu.wprp!Vic3Sampled -filemode -recordtempto $runFolder -instancename $captureSession
if ($LASTEXITCODE -ne 0) { throw 'WPR開始失敗。gameを再開せず、エラーと専用sessionの状態を保存してください' }
$manifest.os_capture.status = 'recording'
[IO.File]::WriteAllText($templatePath, ($manifest | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
wpr -status -instancename $captureSession
wpr -marker "$runId-before-game-resume" -instancename $captureSession
if ($LASTEXITCODE -ne 0) {
    wpr -stop (Join-Path $runFolder 'aborted-before-game.etl') -instancename $captureSession
    throw '開始marker失敗。計測しません。専用sessionの停止を確認してください'
}
```

gameへ戻り、pause解除から6/1でpauseするまでの実時間をBと同じ方法で測る。pause後すぐ同じ管理者端末へ戻る。

```powershell
wpr -marker "$runId-after-game-pause" -instancename $captureSession
$markerExit = $LASTEXITCODE
wpr -status -instancename $captureSession
wpr -stop (Join-Path $runFolder 'cpu.etl') -instancename $captureSession
$stopExit = $LASTEXITCODE
wpr -status -instancename $captureSession
if ($stopExit -ne 0) { throw '停止失敗。専用sessionを確認し、記録を放置しないでください' }
if ($markerExit -ne 0) { throw 'ETLは保存したが終了marker失敗。解析保留です' }
$manifest.os_capture.status = 'saved_unreviewed'
$manifest.os_capture.trace_path = 'cpu.etl'
$manifest.os_capture.trace_sha256 = (Get-FileHash -LiteralPath (Join-Path $runFolder 'cpu.etl') -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($templatePath, ($manifest | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
```

stop/statusの出力もrunFolderへ保存する。**停止前にDropped event=0でも品質確定ではない。** 保存後の警告とETL headerのlost events/buffersを確認する。xperfがある場合は`xperf -i "$runFolder/cpu.etl" -a tracestats`で確認できる。なければWPAのtrace情報と停止出力を確認し、確認できない項目はnullのままにする。失敗traceを良好なrepeatへ数えない。

**中止・crash時:** game側の失敗を記録し、このsessionを`wpr -stop (Join-Path $runFolder 'aborted.etl') -instancename $captureSession`で保存・終了する。stop/statusを確認し、local templateのstatusを`aborted`へ変更する。gameが終了してもWPRが終了したとは限らない。failed runをfinalizeせず、原因確認前に残りの本計測へ進まない。

markerは前後の端末切替を含む**外側境界**。実game区間のtrace上の開始/終了を示す根拠がなければ`exact_game_boundary=unverified`を保つ。traceのpause中をgameのCPU費用へ混ぜない。特定のunpaused区間だけを解析するなら、その区間と境界の不確かさを示し、3か月全体の費用と呼ばない。

## 5. 同runのCSV保存とmanifest確定

gameのpauseと終了日を確認した後、端末で次を実行してからconsoleへ戻り`dump_ticktask_timings`を行う。

```powershell
$dumpBeforeUtc = (Get-Date).ToUniversalTime()
# gameへ戻り dump_ticktask_timings を実行し、受付・書込み成功を確認する。
# 端末へ戻ってから以下を実行する。
$tickCsv = Read-Host '今dumpしたticktask_timings.csvの絶対path'
$csvFile = Get-Item -LiteralPath $tickCsv -ErrorAction Stop
if ($csvFile.LastWriteTimeUtc -lt $dumpBeforeUtc) { throw 'CSVが今回更新されていません。旧CSVは使いません' }
# ETL確認後に記入したlost events/stack/boundary情報を保持するため、diskの最新版を読む。
$manifest = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8 | ConvertFrom-Json
$currentGame = Get-Process -Id $manifest.os_capture.game_pid -ErrorAction Stop
if ($currentGame.StartTime.ToUniversalTime().ToString('o') -ne $manifest.os_capture.process_start_utc) { throw 'game processが変わっています。今回runは保留です' }
Copy-Item -LiteralPath $tickCsv -Destination (Join-Path $runFolder 'ticktask_timings.csv') -ErrorAction Stop
if ($selected[0].capture_mode -eq 'baseline') { $manifest.os_capture.status = 'no_collector' }
[IO.File]::WriteAllText($templatePath, ($manifest | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
```

ここでlocal templateの実設定、Sのlost events/buffers・stack coverage、marker/実game境界の確認結果を記入する。確認できないものはnull/未確認を保ち、notesに理由を残す。lossが確認されたrunは良好な本計測として確定せず保留する。記入後にdiskの最新版を読み直してBOMなしに保存し、finalizeする。古い端末変数からtemplateを上書きしない。

```powershell
$manifest = Get-Content -LiteralPath $templatePath -Raw -Encoding UTF8 | ConvertFrom-Json
[IO.File]::WriteAllText($templatePath, ($manifest | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
$measuredSeconds = Read-Host '今回のpause解除から終了pauseまでの実測秒数'
python tools/finalize_benchmark_run.py $runFolder --wall-clock-seconds $measuredSeconds
if ($LASTEXITCODE -ne 0) { throw 'manifest確定に失敗しました。旧値を転記せず入力を確認してください' }
```

templateの書込みはPowerShell 5.1でもUTF-8 BOMなしに固定している。既に確定した`manifest.json`は再生成しない。CSV更新確認はstale防止の補助であり、同一区間・処理量の証明ではない。

最初のB1/S1を保存できたら、S1のETLが開け、game PID/stackが存在し、同runのCSVが保存できたことを確認する。そこで失敗した場合は残り4回を止め、2件の結果/エラーだけを渡す。

## 6. 6回終了後の既存CLI

```powershell
python tools/check_benchmark_quality.py $batchRoot --matrix (Join-Path $batchRoot 'matrix.json') --json (Join-Path $batchRoot 'quality.json') --markdown (Join-Path $batchRoot 'quality.md') --require-performance-ready
if ($LASTEXITCODE -ne 0) { throw 'hash、境界、repeat、ばらつきの問題をqualityで確認してください。比較は保留です' }
python tools/analyze_benchmarks.py $batchRoot --json (Join-Path $batchRoot 'analysis.json') --markdown (Join-Path $batchRoot 'analysis.md')
if ($LASTEXITCODE -ne 0) { throw '解析失敗。エラーを保存してください' }
```

`ext-baseline`と`ext-sampled`の2群が出る。wall差はobserver overheadの参考値。quality成功は、実際のsettingsが同じこと、正確なtrace/game境界、内部状態同等性、patch速度改善を認定しない。frame/task/callsの境界不一致をtrimして実時間を補正しない。該当runだけ条件を確認し再取得する。

## 7. 渡すもの・解析対象

最初はB1/S1の`manifest.json`・`ticktask_timings.csv`、S1の停止/status結果とtraceの欠落情報だけで収集成立を確認できる。残り終了後は6件のmanifest/CSV、quality/analysis、actual settingsを渡す。旧runと区別する。ETLとsystem全体のexportはlocalに保管する。

原因選定にはSのgame-only CPU/stack export、PID/ASLR/module情報、選んだunpaused区間と境界根拠も必要。WPAでVictoria 3の該当PIDへfilterし、CPU Usage (Sampled)をthread/stack別に見る。ゲームsymbolがなくてもRVAと既存catalogを照合できる。

実exportのheader・単位・timestamp・TID・instruction VA・同PIDのmodule baseを確認して[既存mapping仕様](../../research/os-profile-normalized-schema.md)へ合わせる。CSV列名やvendor schemaを事前に決めつけない。集計表しかなく個別VA/timestampがなければnormalizerへ無理に変換しない。stackは別に保持し、leafのcatalog命中だけでcallerを認定しない。

```powershell
# cpu-samples.csv / mapping.json は実exportを確認して作成したもの。
python tools/normalize_os_profile.py "$runFolder/cpu-samples.csv" --mapping "$runFolder/mapping.json" --run-id $runId --source WPA --output "$runFolder/normalized-cpu.json"
if ($LASTEXITCODE -ne 0) { throw 'normalization失敗。後段へ進みません' }
python tools/correlate_os_profile.py "$runFolder/normalized-cpu.json" --catalog research/generated/os-capture-preparation-2026-10-05/native-region-catalog.json --expected-run-id $runId --output "$runFolder/correlation.json" --markdown "$runFolder/correlation.md"
if ($LASTEXITCODE -ne 0) { throw '既存catalog照合失敗' }
python tools/correlate_os_profile.py "$runFolder/normalized-cpu.json" --catalog research/external-cpu/employment-lookup-catalog.json --expected-run-id $runId --output "$runFolder/lookup-correlation.json" --markdown "$runFolder/lookup-correlation.md"
if ($LASTEXITCODE -ne 0) { throw 'lookup補助catalog照合失敗' }
```

[候補の採否表](../superpowers/reports/2026-10-13-external-cpu-candidate-ja.md)に従う。雇用lookupだけでなく民間投資・移民のcallerも確認する。sampleだけからcall count、allocation頻度、cache bottleneck、Ready/Waitingを決めない。Scheduling/追加観測は、今回の結果で必要な問いが残った場合だけ別途行う。

この手順を終えても性能パッチの実装・同等性検証・安全な適用・実時間A/Bは将来作業。外部調査はIssue #17の解決を待たず進められるが、native profiler Phase4は引き続き独立した未達項目である。

公式参照: [WPR CLI](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options)、[CPU分析](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis)。custom profile構文、filemode、marker、status、stopは公開仕様を確認済み。`-instancename`を含む操作は以前の実機記録があるが、今回のWindows runtimeは未実行。
