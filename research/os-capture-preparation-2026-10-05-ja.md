# 12/16スレッドのOS計測：準備と実行手順

2026-10-05の準備時点の記録。この時点ではユーザーはゲームを操作できず、実ゲームのOS計測は0回だった。その後の実計測は[最初の欠落あり記録](os-capture-attempt-2026-10-05-ja.md)と[欠落0件のsampled記録](os-sampled-capture-2026-10-05-ja.md)を参照。以下のpreflightと未測定templateは準備時点の証拠として残す。CPU stackによる費用の切り分けを最初に行い、必要なら別のmicroarchitecture/allocation計測へ進む。

## 今回確認した状態

- WPR `10.0.26100` とWPA Exporter `11.7.383.39833` が存在。ローカルの `CPU.Verbose.File` はSampledProfile、CSwitch、ReadyThreadのevent/stackを含む。広いGeneralProfileよりこの目的の最初の記録に絞る。[WPR公式仕様](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options)
- ゲームは未起動。この実行環境は管理者ではない。2回の開始確認は `0xc5585011: Failed to enable the policy to profile system performance` で停止。ETLは生成されず、専用sessionも記録中ではない。sandbox外実行でもWindows管理者権限は得られなかった。自動承認レビューの拒否ではない。
- Exporterのhelpは取得できたが、`wpaexporter.deps.json` 不在の警告も出た。実際のexportは未検証。helpの表示を動作成功の証拠にしない。
- AMD uProf CLIはPATHになく、`C:/Program Files/AMD` の直下にも見つからなかった。PC全体の未導入を断定しない。CPU計測だけではcache stall、allocation回数/byte数、inline overflow頻度を測定できない。
- D:/SteamLibraryとE:/Victoria 3のexeを再hashし、解析対象のhashと一致。現在の `アメリカ合衆国_1911_03_01.v3` は266,677,017 bytes、SHA-256 `08d22b19929a5ec480e3e45f4e1eb8ff581b91e1de1b4bdb16512e3d0ea5e949` で、保存済みbench2入力と一致。前の9回が独立にhashを供給したという意味ではない。

確認結果は [preflight.json](generated/os-capture-preparation-2026-10-05/preflight.json)、profileの実内容は [cpu-profile-details.txt](generated/os-capture-preparation-2026-10-05/cpu-profile-details.txt)。installed game、MOD、saveは読み取りだけ。

## 用意したデータ

[capture-plan.json](generated/os-capture-preparation-2026-10-05/capture-plan.json) と [run-templates](generated/os-capture-preparation-2026-10-05/run-templates/) に、warm-up2件、本計測6件を用意した。実行順はwarm-up12/16の後、12→16、16→12、12→16。各本計測では同saveを再loadし、1911/3/1→6/1、同camera/UI・speed・rules・MODで実施する。warm-upは計測区間へ混ぜない。これらは予定であり、全wall time・trace hash・欠損数・module baseは未測定。MOD/rules/speedなど不明な設定はnullで、実測前に確認して記入する。

[native-region-catalog.json](generated/os-capture-preparation-2026-10-05/native-region-catalog.json) は42範囲（経済35、scheduler/初期化/統計7）の専用照合表。根拠JSONとそのbyte hash、RVA範囲、範囲hashを含む。共通helperは重複せず1targetとして保持する。Task/callerへの帰属はstackで判断する。既存230-target TickTask catalogとは別に照合し、単純結合しない。名前 `native_region_0x...` はsource symbolではない。

合成入力84行で各範囲の先頭・末尾byteを既存normalizer/correlatorへ通し、42対象全ての一致、別moduleの除外、範囲間重複0、入力資料のhash一致を確認した。[verification.json](generated/os-capture-preparation-2026-10-05/verification.json) はこの準備検証であり、ゲーム性能測定ではない。

生成・検証に使った研究用source snapshotも保存した。製品toolやnative hookではなく、既存catalog builderとbenchmark template generatorを使う。別の空出力先へ再生成できる:

```powershell
python research/generated/os-capture-preparation-2026-10-05/generation-source.py.txt --repo . --output raw-captures/prep-reproduced
python research/generated/os-capture-preparation-2026-10-05/validation-source.py.txt --repo . --output raw-captures/prep-reproduced
```

この再生成はcatalog/run template/合成検証を作り、preflightやWPRの実行確認は行わない。出力先が空でなければ、書き込み前に拒否する。保存済み出力へ再生成しない。

## 次回の操作：1回目の12スレッド

ゲームを同saveで準備し、warm-up後に再loadして1911/3/1でpause。ゲーム内で実際のTaskThreadCount=12と以前と同じ設定を確認する。既存の `clear_ticktask_timings` / `dump_ticktask_timings` の手順を併用する。ゲーム起動・load・pauseは操作者が行う。

**管理者としてPowerShellを開き、リポジトリrootへ移動してから**次を実行する。rootには `tools/` と `research/` が必要。後続のmarker/stopも同じ端末を使う。既存の他人のWPR sessionはcancelしない。

```powershell
$runId = 'os-cpu-t12-r01'
$repoRoot = (Get-Location).Path
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'tools/correlate_os_profile.py'))) { throw 'リポジトリrootへ移動してください' }
if ($runId -notmatch '^os-cpu-t(12|16)-r0[123]$') { throw '計画にあるrun IDを指定してください' }
$captureIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
$capturePrincipal = [Security.Principal.WindowsPrincipal]::new($captureIdentity)
if (-not $capturePrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw '管理者としてPowerShellを開いてください' }
$gameProcesses = @(Get-Process victoria3 -ErrorAction SilentlyContinue)
if ($gameProcesses.Count -ne 1) { throw 'Victoria 3を1つ起動して計測開始位置でpauseしてください' }
$gameProcess = $gameProcesses[0]
$expectedExe = '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54'
$actualExe = (Get-FileHash -LiteralPath $gameProcess.Path -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualExe -ne $expectedExe) { throw 'exeの版が違うため、この照合表は使えません' }
$runFolder = Join-Path $repoRoot (Join-Path 'raw-captures' $runId)
if (Test-Path -LiteralPath $runFolder) { throw '既存runへ上書きしません。別のrun ID/保存先を用意してください' }
New-Item -ItemType Directory -Path $runFolder | Out-Null
$template = Join-Path $repoRoot "research/generated/os-capture-preparation-2026-10-05/run-templates/$runId/manifest.template.json"
Copy-Item -LiteralPath $template -Destination (Join-Path $runFolder 'manifest.template.json')
$captureSession = "Vic3-$runId"
wpr -start CPU.Verbose -filemode -recordtempto $runFolder -instancename $captureSession
if ($LASTEXITCODE -ne 0) { throw 'WPR開始に失敗。ゲーム計測を始めず、エラーを記録してください' }
wpr -status -instancename $captureSession
```

開始が成功したら、game PID/path、実際の設定、save hashをlocal templateへ記入する。**記録開始のまま放置しない。** CPU.Fileの出力は時間とともに増える。計測を中止する場合も、下記stopで専用sessionを保存・終了する。

開始直前の目印を入れ、ゲームへ戻って3か月の計測を行う。終了日にpauseしてから端末へ戻り、終了目印とstopを実行する。

```powershell
wpr -marker "$runId-before-game-resume" -instancename $captureSession
if ($LASTEXITCODE -ne 0) {
    wpr -stop (Join-Path $runFolder 'aborted-before-game.etl') -instancename $captureSession
    throw '開始marker失敗。ゲームを再開せず、専用sessionが停止したか確認してください'
}
# ここでゲームへ戻り、従来と同じ方法でresumeして1911/6/1でpauseする。
# pause後に端末へ戻り、以下を実行する。
wpr -marker "$runId-after-game-pause" -instancename $captureSession
$markerExitCode = $LASTEXITCODE
wpr -status -instancename $captureSession
wpr -stop (Join-Path $runFolder 'cpu.etl') -instancename $captureSession
if ($LASTEXITCODE -ne 0) { throw 'stop失敗。専用sessionの状態と出力を確認してください' }
if ($markerExitCode -ne 0) { throw 'ETLは保存したが終了markerが失敗。区間の対応を確認するまで解析保留' }
Get-FileHash -LiteralPath (Join-Path $runFolder 'cpu.etl') -Algorithm SHA256
wpr -status -instancename $captureSession
```

markerは端末へ切り替える操作を含む**外側の区間**。marker間時間を3か月のwall timeとして使わない。従来と同じwall計測を別途記録し、WPAでpause中の前後部分を分離する。正確なresume/pauseのtrace時刻が未確認ならその不確かさを残す。チャットの送受信時刻はgame boundaryに使わない。

TickTask CSVを同じrunFolderへ `ticktask_timings.csv` としてコピーし、templateの不明設定と `os_capture` を埋める。ETL hash、WPR表示のdropped events、capture profile、PID、marker、実game boundaryの根拠を記録する。wall timeは実測値を渡し、既存finalizerを使う:

```powershell
# 数値には今回の実測秒数を入れる。前の34.71等は流用しない。
$measuredSeconds = Read-Host '今回の実測秒数（例 34.71、過去値は流用しない）'
python tools/finalize_benchmark_run.py $runFolder --wall-clock-seconds $measuredSeconds
```

16スレッド以降も計画順に同じ手順で実施する。captureあり/なしの差も同条件で別に確認し、collectorの費用を性能差と混同しない。12_r2の過去のextra frame問題を引き継がないよう、CSVの開始/終了frameとtask/callsを毎run確認する。

## 解析へ渡す情報

WPAで `victoria3.exe` をfilterし、CPU Usage (Sampled)をprocess/thread/stack、CPU Usage (Precise)をNew Thread/New Stack/Readying Thread/Readying Stackで確認する。Running、Ready、Waiting、workerの末尾待ちを区別する。範囲一致だけでroot causeを決めない。[Microsoftの分析手順](https://learn.microsoft.com/en-us/troubleshoot/windows-server/support-tools/support-tools-xperf-wpa-wpr)

[WPA Exporter](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/exporter) は保存したanalysis profileと実際のtraceを必要とする。現地helpと公開ページにはoption差があるため、実機helpの `-profile` / `-range` 等を使う。まだ検証していないcolumn名や架空のexport schemaは用意していない。exportにtimestamp、TID、module、instruction VA、該当processのmodule baseがあるか確認する。集計表に個々のtimestamp/VAがなければ、normalizerへ無理に変換しない。必要な詳細viewを別にexportする。

実CSVのheader・unitを確認して [mapping仕様](os-profile-normalized-schema.md) に合わせる。ASLRのbaseはそのrunのimage/module情報から取り、既定image baseを仮定しない。準備したcatalogはそのまま既存correlatorへ渡せる:

```powershell
python tools/normalize_os_profile.py "$runFolder/cpu-samples.csv" --mapping "$runFolder/mapping.json" --run-id $runId --source WPA --output "$runFolder/normalized-cpu.json"
python tools/correlate_os_profile.py "$runFolder/normalized-cpu.json" --catalog research/generated/os-capture-preparation-2026-10-05/native-region-catalog.json --expected-run-id $runId --output "$runFolder/correlation.json" --markdown "$runFolder/correlation.md"
```

最初に雇用のID resolver/pass、移民の24-byte scan/一時配列、共有helperのcaller stackを見る。初期化guardとtick統計更新は本体計算と分ける。CPU sampleの乏しい範囲を「費用ゼロ」と扱わず、allocation頻度やdata latencyが必要なら追加計測を別に設計する。

raw ETLとsystem-wide exportはlocal `raw-captures/` のみ。Gitにはgameでfilterしたsummary、設定、hash、欠損・不確かさを保存する。本書の準備データは、まだ待ち原因・cache bottleneck・speedupを示さない。
