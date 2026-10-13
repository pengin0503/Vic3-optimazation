[CmdletBinding()]
param([uint32]$GamePid=0,[switch]$PrepareOnly)

$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
if(-not [Environment]::Is64BitProcess) { throw 'Use 64-bit PowerShell.' }
Import-Module (Join-Path $PSScriptRoot 'Vic3Diagnostics.psm1') -Force
$Repo=Split-Path -Parent $PSScriptRoot
$SourceCommit=(& git -C $Repo rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0) { throw 'Cannot read source HEAD.' }
$SourceTree=(& git -C $Repo rev-parse 'HEAD^{tree}').Trim()
if($LASTEXITCODE -ne 0) { throw 'Cannot read source tree.' }
$Status=@(& git -C $Repo status --short --untracked-files=all)
if($LASTEXITCODE -ne 0 -or $Status.Count -ne 0) { throw 'Checkout must be clean. Preserve changes; do not force-reset or stage everything.' }
$Catalog=Get-Content -LiteralPath (Join-Path $Repo 'research\native-profiler-runtime-targets-1.14.5.json') -Raw | ConvertFrom-Json
$ExpectedExeHash=$Catalog.executable_sha256
$Build=Join-Path $Repo ('build\diagnostics\'+$SourceCommit.Substring(0,12))
$Loader=Join-Path $Build 'Release\Vic3OptimizationLoader.exe'
$Manifest=Join-Path $Build 'diagnostic-provenance.json'
if(-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
    New-Item -ItemType Directory -Path $Build -Force | Out-Null
    Write-Host 'Preparing the source-matched Windows x64 build and local CTest. No GitHub Actions are started.'
    Invoke-Vic3DiagnosticCommand -File cmake -Arguments @('-S',(Join-Path $Repo 'src\native'),'-B',$Build,'-A','x64') -Log (Join-Path $Build 'configure.log')
    Invoke-Vic3DiagnosticCommand -File cmake -Arguments @('--build',$Build,'--config','Release') -Log (Join-Path $Build 'build.log')
    Invoke-Vic3DiagnosticCommand -File ctest -Arguments @('--test-dir',$Build,'-C','Release','--output-on-failure','--no-tests=error') -Log (Join-Path $Build 'ctest.log')
    $TestLog=Get-Content -LiteralPath (Join-Path $Build 'ctest.log') -Raw
    $Count=[regex]::Match($TestLog,'100% tests passed, 0 tests failed out of (\d+)')
    if(-not $Count.Success -or [int]$Count.Groups[1].Value -lt 1) { throw 'Cannot verify a nonempty successful CTest run.' }
    $BuildCommit=(& git -C $Repo rev-parse HEAD).Trim()
    if($LASTEXITCODE -ne 0 -or $BuildCommit -ne $SourceCommit) { throw 'Source HEAD changed during build; provenance was not written.' }
    $BuildStatus=@(& git -C $Repo status --short --untracked-files=all)
    if($LASTEXITCODE -ne 0 -or $BuildStatus.Count -ne 0) { throw 'Source changed during build; provenance was not written.' }
    $Provenance=[ordered]@{schema_version=1;source_commit=$SourceCommit;source_tree=$SourceTree;loader_sha256=(Get-Vic3DiagnosticHash -Path $Loader);ctest_exit=0;ctest_tests=[int]$Count.Groups[1].Value;verified_utc=[DateTime]::UtcNow.ToString('o')}
    $Provenance | ConvertTo-Json | Out-File -LiteralPath $Manifest -Encoding utf8 -NoClobber
}
$Provenance=Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
Assert-Vic3DiagnosticProvenance -Document $Provenance -SourceCommit $SourceCommit -SourceTree $SourceTree -Loader $Loader
if($PrepareOnly) {
    [pscustomobject]@{source_commit=$SourceCommit;loader=$Loader;loader_sha256=$Provenance.loader_sha256;ctest_tests=$Provenance.ctest_tests;game_accessed=$false}
    return
}
$GamePausedReported=$null
if($GamePid -eq 0) {
    Write-Host 'Use a newly started Victoria 3 process. Load the save and pause it; an already running fresh process is accepted.'
    Read-Host 'Press Enter when ready' | Out-Null
    $GamePausedReported=$true
    Get-Process -Name victoria3 | Select-Object Id,StartTime,Path | Format-List
    $GamePid=[uint32](Read-Host 'New victoria3.exe PID')
}
if($GamePid -eq 0) { throw 'A nonzero PID is required.' }
$Game=Get-Process -Id $GamePid
if($Game.ProcessName -ne 'victoria3' -or [IO.Path]::GetFileName($Game.Path) -ine 'victoria3.exe') { throw 'Wrong process.' }
$GamePath=$Game.Path;$StartUtc=$Game.StartTime.ToUniversalTime();$StartFileTime=$StartUtc.ToFileTimeUtc().ToString([Globalization.CultureInfo]::InvariantCulture)
$ExeHash=Get-Vic3DiagnosticHash -Path $GamePath
if($ExeHash -ne $ExpectedExeHash) { throw 'Unsupported executable hash; no diagnosis performed.' }
$Runs=Join-Path $Repo 'local-data\diagnostics'
$Contexts=@()
if(Test-Path -LiteralPath $Runs) {
    $Contexts=@(Get-ChildItem -LiteralPath $Runs -Filter context.json -Recurse -File | ForEach-Object { Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json })
}
Assert-NewVic3DiagnosticInstance -Contexts $Contexts -GamePid $GamePid -StartFileTime $StartFileTime
$Current=Get-Process -Id $GamePid
if($Current.StartTime.ToUniversalTime() -ne $StartUtc -or $Current.Path -ine $GamePath) { throw 'Process identity changed.' }
$CurrentCommit=(& git -C $Repo rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0 -or $CurrentCommit -ne $SourceCommit) { throw 'Source HEAD changed while preparing the diagnosis.' }
$CurrentStatus=@(& git -C $Repo status --short --untracked-files=all)
if($LASTEXITCODE -ne 0 -or $CurrentStatus.Count -ne 0) { throw 'Source checkout changed while preparing the diagnosis.' }
Assert-Vic3DiagnosticProvenance -Document $Provenance -SourceCommit $SourceCommit -SourceTree $SourceTree -Loader $Loader
$Reservation=New-Vic3DiagnosticAttempt -RunsRoot $Runs -GamePid $GamePid -StartFileTime $StartFileTime
$Run=Join-Path $Runs ([Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Run | Out-Null
[ordered]@{pid=$GamePid;process_start_utc=$StartUtc.ToString('o');process_start_filetime=$StartFileTime;exe_sha256=$ExeHash;source_commit=$SourceCommit;source_tree=$SourceTree;loader_sha256=$Provenance.loader_sha256;mode='diagnose-loadlibrary';attach_attempted=$false;game_paused_reported=$GamePausedReported;attempt_reservation=$Reservation} | ConvertTo-Json | Out-File -LiteralPath (Join-Path $Run 'context.json') -Encoding utf8 -NoClobber
Write-Host "Evidence: $Run"
$SavedPreference=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    & $Loader --diagnose-loadlibrary --pid $GamePid 2>&1 | Out-File -LiteralPath (Join-Path $Run 'diagnose.log') -Encoding utf8 -Width 4096 -ErrorAction Stop
    $DiagnoseExit=$LASTEXITCODE
} finally { $ErrorActionPreference=$SavedPreference }
$DiagnoseExit | Out-File -LiteralPath (Join-Path $Run 'diagnose-exit.txt') -Encoding utf8 -NoClobber
$Log=Get-Content -LiteralPath (Join-Path $Run 'diagnose.log') -Raw
Write-Host $Log
if($DiagnoseExit -notin @(0,8)) {
    [ordered]@{diagnosis_status='not_collected';entry_status='unknown';connection_status='blocked';stage='loader_precondition';exit_code=$DiagnoseExit;attach_attempted=$false} | ConvertTo-Json | Out-File -LiteralPath (Join-Path $Run 'result.json') -Encoding utf8 -NoClobber
    Write-Host "Loader stopped before a structured diagnosis (exit=$DiagnoseExit). Evidence retained; no retry."
    exit $DiagnoseExit
}
$Result=ConvertFrom-Vic3DiagnosticLog -Text $Log -ExitCode $DiagnoseExit -GamePid $GamePid -StartFileTime $StartFileTime
$Result | ConvertTo-Json | Out-File -LiteralPath (Join-Path $Run 'result.json') -Encoding utf8 -NoClobber
if($Result.diagnosis_status -eq 'incomplete') { Write-Host 'Diagnosis incomplete; connection remains blocked. End here; no retry.' }
elseif($Result.connection_status -eq 'blocked') { Write-Host 'Diagnosis collected; connection remains blocked. End here; no attach or retry.' }
else { Write-Host 'Entry probe matched. This is not an attach result. End here.' }
if($DiagnoseExit -ne 0) { exit $DiagnoseExit }
