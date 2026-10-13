$ErrorActionPreference='Stop'
Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
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
    $loader=Join-Path $scratch 'loader.bin';[IO.File]::WriteAllBytes($loader,[byte[]]@(1,2,3))
    $hash=(Get-FileHash -LiteralPath $loader -Algorithm SHA256).Hash.ToLowerInvariant()
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
Write-Host 'Diagnostic workflow: 14 cases passed; no game process accessed.'
