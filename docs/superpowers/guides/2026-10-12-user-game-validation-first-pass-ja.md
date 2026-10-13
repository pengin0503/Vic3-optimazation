# ユーザー側の実ゲーム検証 — 最初はdisabled接続だけ

Date: 2026-10-12 JST

**新しい診断手順:** Issue #17の未解決byte_mismatchには、[注入しないLoadLibraryW診断](2026-10-12-loader-readonly-diagnosis-ja.md)を先に使う。旧artifactは新flagに非対応。新しいLoaderのbuild/provenanceを用意し、診断結果を確認してからAへ進むか判断する。診断exit0をattach成功として扱わない。

**最初に行うのはAのみ。12本の本測定やOS traceはまだ不要。** Aが失敗したらログを保存してそこで止め、同じprocessへの再attach・retryはしない。A成功後にB、A/Bの正常接続・停止が確認できてからCへ進む。read-only profilerは軽量化patchではなく、今回CPU使用率や速度が改善することを期待する検証ではない。


**2026-10-12実測の重要な追記:** 初回disabled attachは `stage=byte_mismatch` / exit 8で失敗。その後、別のゲームプロセスで `LoadLibraryW → MEM_PRIVATE中継領域 → Steam gameoverlayrenderer64.dll` のジャンプ経路が観測された。その後OverlayをOFFと申告した状態でも別のゲームPID16352で`byte_mismatch`/exit8を再現し、さらに別PID9280ではread-onlyで同じSteam DLLへのジャンプ経路が観測された。正常接続は未確認。診断ログ・未解決点・安全な次の検証条件は[実ゲームattach失敗の調査記録](../reports/2026-10-12-game-attach-steam-overlay-byte-mismatch-ja.md)を参照。失敗した同一PIDへ再attachしない。詳細な対照条件と判定は[Issue #17](https://github.com/pengin0503/Vic3-optimazation/issues/17)に記録した。Overlay OFF状態での再現記録をIssueに追記済み。次は安全な接続方式のオフライン設計/検証へ進む。PID9280のLoader接続は未実施であり、code4の解消は未確認。

## 0. 最新診断binaryを用意（ゲーム起動前）

1. [Windows検証run38148690363のartifact](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38148690363/artifacts/11706440529) `native-profiler-validation` をdownloadする。2026-10-12確認時、expired=false。ZIPを展開し、`Release/` 内の次の2filesを同じ作業folder（例 `C:\Vic3Profiler`）へ置く。ゲームのbinariesへ上書きしない。
2. 旧Loader/DLLと取り違えないよう、Get-FileHashで以下を確認する。ZIP内の合成V3PFはgame証拠として使わない。

| ファイル | このartifactのSHA-256 |
| --- | --- |
| Vic3OptimizationLoader.exe | `2abbfcd6e1dcb69a967b3e9a24f7e9270e080767f24a364741636d90f34770bc` |
| Vic3OptimizationProfiler.dll | `39d14473352914bc51d2eb015d3c053604d6f5be45ad058f27402b7ece5e790d` |

binaryのbuild commitは `a101c56a7dcb33b9361677e99f146ae10b3ef831`。これより後のCPU研究commitは診断parser/研究資料の更新を含むが、このLoader/DLL sourceは変更していない。artifactが取得できない場合は[既存build手順](2026-10-05-native-profiler-runtime-validation-ja.md)を使い、自分がbuildしたcommit/hashを記録する。その場合、上表のbinary hashと同一になるとは限らない。

Windows x64、64-bit PowerShell（Windows PowerShell5.1 x64またはPowerShell7）、Visual C++2022 x64 runtimeが必要。loaderが起動しない/依存DLL不足の場合も、その表示を保存し、まだgame attach成功とは扱わない。下のcopy blockは上表artifactの2files専用。自己buildの場合は既存build guideを使い、自分がbuildした実commit/hashに合わせたprovenanceを記録する。

**2026-10-12のPR #16で研究ブランチはmainへ統合済み。** 解析用repositoryは現在の`main`をsource of truthとする。既存cloneに未commit作業がある場合は別cloneでよい。PowerShellでrepository内の変更を確認してから取得する:

```powershell
git status --short
git fetch origin main
git switch main
git pull --ff-only origin main
```

未commit作業があるときにreset/forceで消さない。Python3はtrace解析に使うが、AのLoader接続・停止自体はPython不要。

## A. disabled attach → stop（最初に送る結果）

1. Victoria3を通常起動し、対象saveをloadして一時停止する。
2. Task Manager詳細画面でvictoria3.exeのPIDを自分で確認。PowerShellはゲームと同じ権限で開く。アクセス拒否だけで管理者化やsecurity設定変更を決めない。
3. 下のblockを実行する。入力pathは引用符を付けず入力。save pathは実際にloadした初期saveを指定する。

```powershell
if (-not [Environment]::Is64BitProcess) { throw '64-bit PowerShellで実行する' }
$Repo = (Resolve-Path -LiteralPath (Read-Host '研究branchのrepository folder') -ErrorAction Stop).Path
$Bin = (Resolve-Path -LiteralPath (Read-Host 'LoaderとDLLを置いたfolder') -ErrorAction Stop).Path
$Loader = Join-Path $Bin 'Vic3OptimizationLoader.exe'
$Dll = Join-Path $Bin 'Vic3OptimizationProfiler.dll'
$LoaderHash = (Get-FileHash -LiteralPath $Loader -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
$DllHash = (Get-FileHash -LiteralPath $Dll -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
# 上表のartifactを利用する場合のみ、この2条件を照合する。自己buildならそのprovenanceを記録する。
if ($LoaderHash -ne '2abbfcd6e1dcb69a967b3e9a24f7e9270e080767f24a364741636d90f34770bc' -or $DllHash -ne '39d14473352914bc51d2eb015d3c053604d6f5be45ad058f27402b7ece5e790d') { throw 'artifactとbinary hashが異なる。使用binaryを確認する' }
$gamePid = [int](Read-Host '確認したvictoria3.exeのPID')
$Game = Get-Process -Id $gamePid -ErrorAction Stop
if ($Game.ProcessName -ne 'victoria3') { throw '選択したPIDはvictoria3ではない' }
$ExeHash = (Get-FileHash -LiteralPath $Game.Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
if ($ExeHash -ne '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54') { throw '対象1.14.5 exe hashと異なる。attachせずhashとversionを記録する' }
$Save = (Resolve-Path -LiteralPath (Read-Host 'loadした初期save fileのpath') -ErrorAction Stop).Path
$Run = Join-Path $Repo ('local-data\game-smoke\disabled-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Run -ErrorAction Stop | Out-Null
Get-FileHash -LiteralPath $Game.Path,$Save,$Loader,$Dll -Algorithm SHA256 | Format-List | Out-File (Join-Path $Run 'identity.log') -Encoding utf8
[pscustomobject]@{ pid=$gamePid; process_start_utc=$Game.StartTime.ToUniversalTime().ToString('o'); game_path=$Game.Path; loader_sha256=$LoaderHash; dll_sha256=$DllHash; profiler_source_commit='a101c56a7dcb33b9361677e99f146ae10b3ef831'; mode='disabled'; smoke_only=$true } | ConvertTo-Json | Out-File (Join-Path $Run 'context.json') -Encoding utf8
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber | Format-List | Out-File (Join-Path $Run 'windows.log') -Encoding utf8
try {
    $ModuleRows = @($Game.Modules | Where-Object { $_.ModuleName -in @('kernel32.dll','KernelBase.dll') })
    if ($ModuleRows.Count -eq 0) { throw 'kernel32/KernelBase module情報を取得できない' }
    $ModuleRows | Select-Object ModuleName,FileName,ModuleMemorySize | Format-List | Out-File (Join-Path $Run 'modules.log') -Encoding utf8
} catch {
    $_ | Out-File (Join-Path $Run 'modules-error.log') -Encoding utf8
    throw 'module情報取得が失敗。errorを保存してここで停止する'
}
$Trace = Join-Path $Run 'capture.v3pf'
& $Loader --pid $gamePid --dll $Dll --disabled --output $Trace 2>&1 | Out-File (Join-Path $Run 'attach.log') -Encoding utf8 -Width 4096
$AttachExit = $LASTEXITCODE
$AttachExit | Out-File (Join-Path $Run 'attach-exit.txt') -Encoding utf8
Get-Content (Join-Path $Run 'attach.log')
Write-Host "Attach exit=$AttachExit; evidence=$Run"
```

module情報の取得が失敗した場合は、そのerrorも保存する。Process情報やhashが取得できなければそこで止める。exe hashが違う場合、バージョン名だけが同じでもこのbinaryをattachしない。

**attach exit0かつ `Profiler ready; enabled mask=0; ...` の場合だけ**、次のstop blockを実行する。Aではゲーム時間を進める必要はない。

```powershell
if ($AttachExit -ne 0) { throw 'attach未成功。このprocessへstop/再attachせず、失敗ログを保存する' }
& $Loader --stop --pid $gamePid 2>&1 | Out-File (Join-Path $Run 'stop.log') -Encoding utf8 -Width 4096
$StopExit = $LASTEXITCODE
$StopExit | Out-File (Join-Path $Run 'stop-exit.txt') -Encoding utf8
Get-Content (Join-Path $Run 'stop.log')
if ($StopExit -ne 0) { throw 'stop失敗。ログとtraceを保持し、このprocessへ再attachしない' }
$TracePython = (Get-Command python -CommandType Application -ErrorAction Stop).Source
& $TracePython (Join-Path $Repo 'tools\parse_native_profiler_trace.py') $Trace --output (Join-Path $Run 'parsed.json') --expected-executable-sha256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54
$ParseExit = $LASTEXITCODE
$ParseExit | Out-File (Join-Path $Run 'parse-exit.txt') -Encoding utf8
if (Test-Path -LiteralPath $Trace) { Get-FileHash -LiteralPath $Trace -Algorithm SHA256 | Format-List | Out-File (Join-Path $Run 'trace-hash.log') -Encoding utf8 }
if (-not (Test-Path -LiteralPath (Join-Path $Run 'parsed.json'))) { throw 'parser出力なし。parse成功とせずtrace/logを保存する' }
```

Pythonが使えない場合はstopまでのlogsとraw traceを送ればよい。parser未実行をexit0と記録せず、こちらで解析する。

期待するstop表示は `Profiler stopped and capture finalized. DLL remains loaded and inert.`。parser exit0だけでは合格ではない。parsed.jsonのheader_valid/segment_complete、metadata.disabled=true、enabled_target_mask=0、diagnostics、Counter1/3/4を確認する。署名失敗counter等が非zeroなら実測gateはblocked。AでFunctionBegin/Endは不要で、hookイベントがあれば異常。

### Aで送るもの

- `$Run` 内のidentity/context/windows/modules、attach/exit、取得できたstop/parse/trace hashのlogsとJSON。
- `capture.v3pf` があれば同じfolderへ含める。失敗時にtraceが存在しないのはあり得る。
- 「ゲーム一時停止中」「実際のversion」「crash/エラー表示」の簡単な説明。

そのfolderだけZIP化して送る。game exe/DLL/初期save本体はこの最初のpacketに不要。既に送ったGPU3-session JSONも不要。

`Attach failed (no retry), code4` と `Unsupported process/build ... Gate code:4` は別の失敗。前者なら **Module resolution diagnostics v2の全文**を保存する。stage/error/path/base/size/RVA/protection/bytes_readが原因切り分けの材料。失敗後のfallback・再試行・部分targetsによる成功扱いはしない。timeout等でDLLが残っている可能性もあるため、次回はゲームを終了して新しいprocessから行う。

## B. 3targets enabledの短い接続検証（A確認後）

ゲームを再起動して同じ初期saveをloadし、一時停止。Aのprocess選択/hash/context準備を新しいPID・新しい `$Run` で行う。**Aのblockを丸ごと再実行してdisabled attachした後にenabledを試すことはしない。** 準備部分までを再利用し、folder prefixをenabled、context.jsonのmodeをenabledへ変更し、attach commandを次へ置換する:

```powershell
& $Loader --pid $gamePid --dll $Dll --targets investment,migration,employment --output $Trace 2>&1 | Out-File (Join-Path $Run 'attach.log') -Encoding utf8 -Width 4096
$AttachExit = $LASTEXITCODE
$AttachExit | Out-File (Join-Path $Run 'attach-exit.txt') -Encoding utf8
```

exit0/ready mask7のときだけ短い区間（例1ゲーム内月程度）を進めて再びpauseし、Aと同じstop/parse blockを実行する。日付区間を記録する。全3targetsのfunction pairs、drop/sequence/broken diagnostics、Counter1/3/4、crashを確認する。1月で必要targetsが実行されなければ、そのtraceは不足として保存する。これは接続smokeで、overhead比較の本測定runには数えない。

## C. 本測定と安定性（A/B成功後）

[Phase4実測handoff](2026-10-12-phase4-runtime-evidence-handoff-ja.md)に従い、12/16 threads × disabled/enabled ×各3回以上の**最低12本の本測定**を取得する。各runはfresh process、同一初期save/hash・camera/UI・speed・設定・区間、同じwarm-up、各thread条件でmode交互。必要ならvanilla対照でDLL自体の費用も分離する。

同じrunのCSV・wall time・V3PF・成功attach/stopに、正確なresume/pause区間・clock alignmentを裏付けるOS traceとRunning/Ready/Waiting・loss statisticsを対応付ける。[OS手順](../../../research/os-profiling-plan.md)と[focused WPR guide](../../../research/os-sampled-capture-2026-10-05-ja.md)を再利用する。外側manual markersだけでexact boundariesをtrueにしない。初回から12本すべてを取得する必要はなく、まず代表1runでOS/CSV区間の対応方法を確認してから本反復へ進む。

終了save・再起動/reload・crashや異常進行の記録も残す。初期save hash一致だけで長時間安定性を合格としない。通常の進行でsave bytesが変わること自体は異常ではない。native/CSVのscope、overhead対ノイズ、OS状態、save/reloadの分析を証拠hashへ結び付ける。

新しいgame version、非対応hash、attach/stop失敗、区間不一致、drop/不明stateは成功とせず記録する。GPU実機の常駐pipeline研究や性能patchの導入はこの実ゲーム接続確認に不要。

## この手順の検証範囲

2026-10-12時点のartifact APIと既存Windows10/10検証・binary hash記録、Loader CLI/ready/stop出力、Python parser引数を照合した。ここでgame/PowerShell実行を確認したものではない。対象WindowsでのA/B/Cは未実施。今回の追加は文書と再現コマンド修正のみで、既存native binaryは再build/CI rerunしない。
