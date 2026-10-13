$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
Import-Module (Join-Path $PSScriptRoot '..\Vic3Diagnostics.psm1') -Force
function Assert-True($Value,$Name) { if(-not $Value){throw "Failed: $Name"} }
function Assert-Rejects([scriptblock]$Action,$Name) {
    $rejected=$false;try { & $Action | Out-Null } catch { $rejected=$true }
    Assert-True $rejected $Name
}
$modified=@'
Module resolution diagnostics v3: stage=byte_mismatch win32_error=0 pe_error=0
owner_path=C:\WINDOWS\System32\KERNEL32.DLL bytes_read=16
requested_pid=24516 handle_pid=24516 process_start_filetime=134363317251906048
probe_available=1 first_mismatch=0 mismatch_count=5
diagnosis_status=complete entry_status=modified connection_status=blocked
Read-only diagnosis only; no DLL injected; not an attach result.
'@
$result=ConvertFrom-Vic3DiagnosticLog -Text $modified -ExitCode 0 -GamePid 24516 -StartFileTime '134363317251906048'
Assert-True ($result.diagnosis_status -eq 'complete' -and $result.connection_status -eq 'blocked') 'complete modified is not attach success'
Assert-Rejects { ConvertFrom-Vic3DiagnosticLog -Text $modified -ExitCode 0 -GamePid 14956 -StartFileTime '134363317251906048' } 'wrong PID'
Assert-Rejects { ConvertFrom-Vic3DiagnosticLog -Text $modified -ExitCode 0 -GamePid 24516 -StartFileTime '134363317251906049' } 'FILETIME exact beyond double precision'
Assert-Rejects { ConvertFrom-Vic3DiagnosticLog -Text $modified -ExitCode 8 -GamePid 24516 -StartFileTime '134363317251906048' } 'contradictory exit'
$contradictory=$modified.Replace('stage=byte_mismatch','stage=none').Replace('entry_status=modified connection_status=blocked','entry_status=matched connection_status=entry_probe_passed')
Assert-Rejects { ConvertFrom-Vic3DiagnosticLog -Text $contradictory -ExitCode 0 -GamePid 24516 -StartFileTime '134363317251906048' } 'matched cannot contain mismatches'
$matched=$contradictory.Replace('first_mismatch=0 mismatch_count=5','first_mismatch=16 mismatch_count=0')
Assert-True ((ConvertFrom-Vic3DiagnosticLog -Text $matched -ExitCode 0 -GamePid 24516 -StartFileTime '134363317251906048').entry_status -eq 'matched') 'matched entry remains diagnostic only'
Assert-Rejects { ConvertFrom-Vic3DiagnosticLog -Text ($modified.Replace('diagnosis_status=complete','diagnosis_status=incomplete')) -ExitCode 0 -GamePid 24516 -StartFileTime '134363317251906048' } 'incomplete cannot be complete'
$past=@([pscustomobject]@{pid=24516;process_start_filetime='134363317251906048'})
Assert-Rejects { Assert-NewVic3DiagnosticInstance -Contexts $past -GamePid 24516 -StartFileTime '134363317251906048' } 'same process cannot repeat'
Assert-NewVic3DiagnosticInstance -Contexts $past -GamePid 24516 -StartFileTime '134363317251906049'
Assert-NewVic3DiagnosticInstance -Contexts $past -GamePid 14956 -StartFileTime '134363317251906048'
$scratch=Join-Path ([IO.Path]::GetTempPath()) ('vic3-workflow-test-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $scratch | Out-Null
try {
    # Reservation is atomic even when two callers pass the earlier history check.
    $reservation=New-Vic3DiagnosticAttempt -RunsRoot $scratch -GamePid 24516 -StartFileTime '134363317251906048'
    Assert-True (Test-Path -LiteralPath $reservation) 'first reservation created'
    Assert-Rejects { New-Vic3DiagnosticAttempt -RunsRoot $scratch -GamePid 24516 -StartFileTime '134363317251906048' } 'concurrent or repeated reservation denied'
    New-Vic3DiagnosticAttempt -RunsRoot $scratch -GamePid 24516 -StartFileTime '134363317251906049' | Out-Null
    $loader=Join-Path $scratch 'loader.bin';[IO.File]::WriteAllBytes($loader,[byte[]]@(1,2,3))
    Assert-True ((Get-Vic3DiagnosticHash -Path $loader) -eq '039058c6f2c0cb492c533b0a4d14ef77cc0f78abccced5287d84a1a2011cfb81') 'SHA256 independent of ambient Get-FileHash availability'
    $hash=Get-Vic3DiagnosticHash -Path $loader
    $provenance=[pscustomobject]@{schema_version=1;source_commit=('a'*40);source_tree=('b'*40);loader_sha256=$hash;ctest_exit=0;ctest_tests=10}
    Assert-Vic3DiagnosticProvenance -Document $provenance -SourceCommit ('a'*40) -SourceTree ('b'*40) -Loader $loader
    Assert-Rejects { Assert-Vic3DiagnosticProvenance -Document $provenance -SourceCommit ('c'*40) -SourceTree ('b'*40) -Loader $loader } 'old source cannot use new binary'
    $provenance.ctest_tests=0
    Assert-Rejects { Assert-Vic3DiagnosticProvenance -Document $provenance -SourceCommit ('a'*40) -SourceTree ('b'*40) -Loader $loader } 'zero tests'
    $provenance.ctest_tests=10;[IO.File]::WriteAllBytes($loader,[byte[]]@(4,5,6))
    Assert-Rejects { Assert-Vic3DiagnosticProvenance -Document $provenance -SourceCommit ('a'*40) -SourceTree ('b'*40) -Loader $loader } 'tampered binary'
} finally {
    $resolved=(Resolve-Path -LiteralPath $scratch).Path
    if([IO.Path]::GetDirectoryName($resolved) -ne [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')) { throw 'Unexpected test scratch path' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
# Execute the actual wrapper's terminal statements in a child host, without a game.
$tokens=$null;$errors=$null
$entry=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot '..\Invoke-Vic3Diagnostics.ps1'),[ref]$tokens,[ref]$errors)
$ready=$entry.EndBlock.Statements | Where-Object { $_ -is [System.Management.Automation.Language.IfStatementAst] -and $_.Clauses[0].Item1.Extent.Text -eq '$GamePid -eq 0' } | Select-Object -First 1
$context=$entry.Find({param($n) $n -is [System.Management.Automation.Language.HashtableAst] -and $n.Extent.Text -like '*game_paused_reported*'},$true)
$pauseField=$context.KeyValuePairs | Where-Object { $_.Item1.SafeGetValue() -eq 'game_paused_reported' } | Select-Object -First 1
foreach($candidate in @(24516,0)) {
    $report=& {
        param($gameInput,$readyText,$pauseText)
        $GamePid=$gameInput;$GamePausedReported=$null
        function Read-Host { '24516' }
        function Get-Process { param($Name) @() }
        . ([ScriptBlock]::Create($readyText))
        [pscustomobject]@{pause=(. ([ScriptBlock]::Create($pauseText)))}
    } $candidate $ready.Extent.Text $pauseField.Item2.Extent.Text
    if($candidate -eq 0){Assert-True ($report.pause -eq $true) 'interactive acknowledgement recorded'}
    else {Assert-True ($null -eq $report.pause) 'explicit PID does not invent pause acknowledgement'}
}
$save=$entry.EndBlock.Statements | Where-Object { $_.Extent.Text -like '*Out-File*result.json*' } | Select-Object -Last 1
$terminal=($entry.EndBlock.Statements | Where-Object { $_.Extent.StartOffset -gt $save.Extent.EndOffset } | ForEach-Object { $_.Extent.Text }) -join "`n"
$childHost=(Get-Process -Id $PID).Path
foreach($expected in @(0,8)) {
    $setup='$Result=[pscustomobject]@{connection_status="blocked";diagnosis_status="'+$(if($expected -eq 0){'complete'}else{'incomplete'})+'"};$DiagnoseExit='+$expected+';'
    $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($setup+$terminal))
    & $childHost -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand $encoded | Out-Null
    Assert-True ($LASTEXITCODE -eq $expected) 'wrapper preserves diagnostic exit code'
}
Write-Host 'Diagnostic workflow: 22 cases passed; no game process accessed.'
