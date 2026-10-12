# 次回の実ゲーム検証：注入せずLoadLibraryWを診断する

Date: 2026-10-12 JST

**この手順は診断だけを行う。DLL注入・stop・enabled計測は実施しない。** 実ゲームの成功確認はまだない。Issue #17の接続拒否は残る。[実装報告](../reports/2026-10-12-loader-readonly-byte-mismatch-ja.md)と[設計比較](../specs/2026-10-12-loader-readonly-byte-mismatch-design.md)も参照。

## 1. 新Loaderを用意する

新ブランチ `fix/loader-readonly-byte-mismatch` または対応PRを取得し、作業用フォルダでbuildする。既存成果、ゲーム/Workshop/MODへ上書きしない。旧first-pass guideの `a101c56...` artifactは診断v2であり、今回の新flagを持たない。旧artifactのhashを新binaryに適用しない。

```powershell
git status --short
git fetch origin fix/loader-readonly-byte-mismatch
git switch fix/loader-readonly-byte-mismatch
git pull --ff-only origin fix/loader-readonly-byte-mismatch
# Visual Studio 2022の場合。Visual Studio 2026なら -G 'Visual Studio 18 2026' を追加する。
cmake -S src/native -B build/native -A x64
if ($LASTEXITCODE -ne 0) { throw 'configure失敗' }
cmake --build build/native --config Release
if ($LASTEXITCODE -ne 0) { throw 'build失敗' }
ctest --test-dir build/native -C Release --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'native検証失敗' }
```

未commitの作業があるcloneは変更せず、別cloneを使う。診断には `build/native/Release/Vic3OptimizationLoader.exe` だけを使用する。Profiler DLLは診断modeではロードしない。自己buildのcommit/hashを以下で記録する。PR CI artifactを使う場合はartifactのrun URL/head commitも記録し、同じ名前の古いLoaderと混ぜない。

## 2. fresh PIDで1回のread-only診断

ゲームを通常起動し、対象saveをloadして一時停止する。Steam Overlayの申告設定も記録するが、OFFでフックが消えるとは仮定しない。既にattach失敗したPIDは再attachせず、今回もfresh processを使う。同じ権限の64-bit PowerShellで実行する。

```powershell
if (-not [Environment]::Is64BitProcess) { throw '64-bit PowerShellで実行する' }
$Repo = (Resolve-Path -LiteralPath (Read-Host '新Loaderをbuildしたrepository folder') -ErrorAction Stop).Path
$Loader = Join-Path $Repo 'build\native\Release\Vic3OptimizationLoader.exe'
if (-not (Test-Path -LiteralPath $Loader -PathType Leaf)) { throw '新Loaderがない' }
$gamePid = [uint32](Read-Host '確認したvictoria3.exeのPID')
$Game = Get-Process -Id $gamePid -ErrorAction Stop
if ($Game.ProcessName -ne 'victoria3') { throw '対象外process' }
$ExeHash = (Get-FileHash -LiteralPath $Game.Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
if ($ExeHash -ne '9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54') { throw '対応exe hashではない。診断を実行しない' }
$SourceCommit = (& git -C $Repo rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'source commitを取得できない' }
$SourceStatus = @(& git -C $Repo status --short)
if ($LASTEXITCODE -ne 0 -or $SourceStatus.Count -ne 0) { throw 'clean checkoutの検証済みbuildを使う' }
$OverlaySetting = Read-Host 'Steam Overlayの申告設定（ON/OFF/不明）'
$Run = Join-Path $Repo ('local-data\game-smoke\diagnose-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Run -ErrorAction Stop | Out-Null
$LoaderHash = (Get-FileHash -LiteralPath $Loader -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
[pscustomobject]@{
    pid=$gamePid; process_start_utc=$Game.StartTime.ToUniversalTime().ToString('o')
    exe_sha256=$ExeHash; loader_sha256=$LoaderHash; source_commit=$SourceCommit
    mode='diagnose-loadlibrary'; overlay_setting_reported=$OverlaySetting
    game_paused=$true; attach_attempted=$false
} | ConvertTo-Json | Out-File (Join-Path $Run 'context.json') -Encoding utf8
& $Loader --diagnose-loadlibrary --pid $gamePid 2>&1 | Out-File (Join-Path $Run 'diagnose.log') -Encoding utf8 -Width 4096
$DiagnoseExit = $LASTEXITCODE
$DiagnoseExit | Out-File (Join-Path $Run 'diagnose-exit.txt') -Encoding utf8
Get-Content (Join-Path $Run 'diagnose.log')
Write-Host "Diagnose exit=$DiagnoseExit; evidence=$Run"
# ここで終了。stop/attach/enabledを続けて実行しない。
```

使用したbinaryが本当にそのsourceからbuildされたかは、source commitとhash記録だけでは自動的に証明されない。上のbuild直後のbinaryを選び、配布artifactならartifactのprovenanceを合わせる。

## 3. 判定と送る証拠

- exit0 / `stage=none` / `Export probe matched`: 入口検査に合格した診断。**attach成功ではない**。続けて注入せず、結果を確認してから別fresh PIDで既存A手順へ進むか判断する。
- exit8 / `stage=byte_mismatch`: 想定される拒否。v3全文の `requested_pid` と `handle_pid`、`process_start_filetime`、byte列、first_mismatch、remote_entry、branch_target、branch属性を保存する。`win32_error=0`はOSエラーのないpolicy拒否を示す。
- その他のstage/exit、使用方法表示、起動失敗: そのままログを保存する。管理者化・security設定変更・強制注入で埋め合わせない。

`process_start_filetime`は1601-01-01 UTCからの100ns単位。PowerShellでは `[DateTime]::FromFileTimeUtc([long]$value).ToString('o')` でcontextの開始時刻と照合できる。診断が採取したhandleのPID/開始時刻とcontextが一致しなければ、別processの証拠として扱う。ASLRアドレスは各PIDの観測値であり、過去PIDと同一アドレスでも同じprocessとは判定しない。

`probe_available=0`ではbyte証拠なし。`first_mismatch=16`は差分なし、または比較未実施のsentinelなのでprobe_availableとstageを併読する。`remote_entry=rel32_jump`は先頭がE9の観測のみ。`branch_type=131072`はMEM_PRIVATE、`16777216`はMEM_IMAGE。queryが成功してもfree/uncommitted領域の場合がある。`branch_query_available=0`ではquery未実施/失敗を区別するためremote_entryとbranch_query_errorを確認する。

この版は最初の行先の属性までを採る。private中継からSteamへの二段目は追わず、DLL名、署名、悪性、フック設置主体を判定しない。FF25/REX/他opcodeはunknown。追加query失敗が元のbyte_mismatchを変更しないことも確認する。

送るものは新しい `$Run` のcontext/diagnose/exitだけでよい。絶対パス等の個人情報がログにあれば共有前に確認する。exe・save・DLL本体や全PCのログは不要。新しい同一PIDの結果が得られるまで、実ゲーム接続成功、Phase 4、CPU高速化は未確認のまま。
