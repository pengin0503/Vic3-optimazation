Set-StrictMode -Version Latest
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop

function Get-Vic3DiagnosticHash {
    param([string]$Path)
    $stream=[IO.File]::OpenRead($Path)
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try { ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose();$stream.Dispose() }
}

function Assert-Vic3DiagnosticProvenance {
    param($Document,[string]$SourceCommit,[string]$SourceTree,[string]$Loader)
    if($Document.schema_version -ne 1 -or $Document.source_commit -ne $SourceCommit -or
       $Document.source_tree -ne $SourceTree -or $Document.ctest_exit -ne 0 -or $Document.ctest_tests -lt 1) {
        throw 'Build provenance does not match this source or a successful nonempty CTest run.'
    }
    if(-not (Test-Path -LiteralPath $Loader -PathType Leaf) -or
       (Get-Vic3DiagnosticHash -Path $Loader) -ne $Document.loader_sha256) {
        throw 'Loader is missing or its hash differs from the verified build.'
    }
}

function Assert-NewVic3DiagnosticInstance {
    param([object[]]$Contexts=@(),[uint32]$GamePid,[string]$StartFileTime)
    foreach($context in $Contexts) {
        if([uint32]$context.pid -eq $GamePid -and [string]$context.process_start_filetime -eq $StartFileTime) {
            throw 'This process instance already has a diagnostic attempt. Keep its evidence and use a new game process.'
        }
    }
}

function New-Vic3DiagnosticAttempt {
    param([string]$RunsRoot,[uint32]$GamePid,[string]$StartFileTime)
    if(-not $GamePid -or $StartFileTime -notmatch '^\d+$') { throw 'Invalid process instance key.' }
    $directory=Join-Path $RunsRoot '.attempts'
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $marker=Join-Path $directory ($GamePid.ToString()+'-'+$StartFileTime+'.json')
    # CreateNew is an atomic reservation, including across independent hosts.
    $stream=[IO.File]::Open($marker,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {
        $record=[ordered]@{pid=$GamePid;process_start_filetime=$StartFileTime;reserved_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json
        $bytes=[Text.Encoding]::UTF8.GetBytes($record);$stream.Write($bytes,0,$bytes.Length)
    } finally { $stream.Dispose() }
    $marker
}

function ConvertFrom-Vic3DiagnosticLog {
    param([string]$Text,[int]$ExitCode,[uint32]$GamePid,[string]$StartFileTime)
    $identity=[regex]::Match($Text,'(?m)^requested_pid=(\d+) handle_pid=(\d+) process_start_filetime=(\d+)\s*$')
    if(-not $identity.Success -or [uint32]$identity.Groups[1].Value -ne $GamePid -or
       [uint32]$identity.Groups[2].Value -ne $GamePid -or $identity.Groups[3].Value -ne $StartFileTime) {
        throw 'Diagnostic PID/start time does not match the selected process instance.'
    }
    $status=[regex]::Match($Text,'(?m)^diagnosis_status=(complete|incomplete) entry_status=(matched|modified|unknown) connection_status=(entry_probe_passed|blocked)\s*$')
    $stage=[regex]::Match($Text,'(?m)^Module resolution diagnostics v3: stage=(\w+) win32_error=(\d+) pe_error=(\d+)\s*$')
    if(-not $status.Success -or -not $stage.Success) { throw 'Missing structured diagnosis result; use the source-matched verified build.' }
    $complete=$status.Groups[1].Value -eq 'complete'
    $entry=$status.Groups[2].Value;$connection=$status.Groups[3].Value
    if($complete) {
        $probe=[regex]::Match($Text,'(?m)^probe_available=1 first_mismatch=(\d+) mismatch_count=(\d+)\s*$')
        $consistentProbe=$probe.Success -and
            (($entry -eq 'matched' -and $probe.Groups[1].Value -eq '16' -and $probe.Groups[2].Value -eq '0') -or
             ($entry -eq 'modified' -and [int]$probe.Groups[1].Value -lt 16 -and [int]$probe.Groups[2].Value -ge 1 -and [int]$probe.Groups[2].Value -le 16))
        if($ExitCode -ne 0 -or $stage.Groups[2].Value -ne '0' -or $stage.Groups[3].Value -ne '0' -or
           -not $consistentProbe -or $Text -notmatch '\bbytes_read=16\b' -or
           -not (($entry -eq 'matched' -and $stage.Groups[1].Value -eq 'none' -and $connection -eq 'entry_probe_passed') -or
                 ($entry -eq 'modified' -and $stage.Groups[1].Value -eq 'byte_mismatch' -and $connection -eq 'blocked'))) {
            throw 'Contradictory diagnostic completion or connection policy result.'
        }
    } elseif($ExitCode -ne 8 -or $entry -ne 'unknown' -or $connection -ne 'blocked') {
        throw 'Incomplete diagnosis must retain a failure exit and blocked policy.'
    }
    [pscustomobject]@{diagnosis_status=$status.Groups[1].Value;entry_status=$entry;connection_status=$connection;stage=$stage.Groups[1].Value;exit_code=$ExitCode;attach_attempted=$false}
}

function Invoke-Vic3DiagnosticCommand {
    param([string]$File,[string[]]$Arguments,[string]$Log)
    $command=Get-Command $File -ErrorAction Stop
    $saved=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $command.Source @Arguments 2>&1 | Out-File -LiteralPath $Log -Encoding utf8 -Width 4096 -ErrorAction Stop
        $result=$LASTEXITCODE
    } finally { $ErrorActionPreference=$saved }
    if($result -ne 0) { throw "Command failed (exit=$result). Read $Log" }
}
Export-ModuleMember -Function Get-Vic3DiagnosticHash,Assert-Vic3DiagnosticProvenance,Assert-NewVic3DiagnosticInstance,New-Vic3DiagnosticAttempt,ConvertFrom-Vic3DiagnosticLog,Invoke-Vic3DiagnosticCommand
