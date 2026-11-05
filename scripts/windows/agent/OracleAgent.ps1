#Requires -Version 5.1
<#
.SYNOPSIS
    Queue worker for the Windows oracle VM.

.DESCRIPTION
    Polls C:\work\in for job directories, renders each document.docx to
    document.pdf via RenderOne.ps1, and shuts the VM down once the queue has
    been empty for a while.

    Started from the Startup folder of the auto-logon user. It must run inside
    the interactive desktop session: Word COM fails in a service or SSH
    session, which has no desktop.

    Protocol:
        in\<jobid>\document.docx        input
        out\<jobid>\document.pdf        output
        out\<jobid>\result.json         timing, word version, error
        out\<jobid>\DONE | FAIL         terminal marker
        C:\work\STOP                    present -> do not shut down
#>
[CmdletBinding()]
param(
    [string]$InDir = 'C:\work\in',
    [string]$OutDir = 'C:\work\out',
    [string]$AgentDir = 'C:\work\agent',
    [int]$DocTimeoutSeconds = 180,
    [int]$IdleSeconds = 45,
    [switch]$NoShutdown
)

$ErrorActionPreference = 'Stop'
$logPath = Join-Path $AgentDir 'agent.log'
$statusPath = Join-Path $AgentDir 'status.json'
$stopFile = Join-Path 'C:\work' 'STOP'
$renderOne = Join-Path $AgentDir 'RenderOne.ps1'

function Write-Log {
    param([string]$Message)
    $line = '{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -Path $logPath -Value $line -ErrorAction SilentlyContinue
}

function Get-WordVersion {
    $k = 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration'
    return (Get-ItemProperty -Path $k -Name VersionToReport -ErrorAction SilentlyContinue).VersionToReport
}

function Write-Status {
    param([string]$State, [string]$Current, [int]$Done, [int]$Failed, [int]$Pending)
    $s = [ordered]@{
        state       = $State
        current     = $Current
        pending     = $Pending
        done        = $Done
        failed      = $Failed
        wordVersion = (Get-WordVersion)
        machine     = $env:COMPUTERNAME
        updatedAt   = (Get-Date).ToString('o')
    }
    try { ($s | ConvertTo-Json) | Set-Content -Path $statusPath -Encoding UTF8 } catch { }
}

New-Item -ItemType Directory -Force -Path $InDir, $OutDir, $AgentDir | Out-Null
Write-Log ('agent start; word={0}; timeout={1}s; idle={2}s' -f (Get-WordVersion), $DocTimeoutSeconds, $IdleSeconds)
Write-Status -State 'starting' -Current '' -Done 0 -Failed 0 -Pending 0

$done = 0
$failed = 0
$lastActivity = Get-Date
$reason = 'idle'

while ($true) {
    if (Test-Path -LiteralPath $stopFile) {
        $reason = 'stop-file'
        Write-Log 'STOP file present, not shutting down'
        break
    }

    $jobs = @(Get-ChildItem -Path $InDir -Directory -ErrorAction SilentlyContinue)
    $pending = @()
    foreach ($job in $jobs) {
        if (-not (Test-Path -LiteralPath (Join-Path $job.FullName 'document.docx'))) { continue }
        $outJob = Join-Path $OutDir $job.Name
        if (Test-Path -LiteralPath (Join-Path $outJob 'DONE')) { continue }
        if (Test-Path -LiteralPath (Join-Path $outJob 'FAIL')) { continue }
        $pending += $job
    }

    if ($pending.Count -eq 0) {
        $idle = ((Get-Date) - $lastActivity).TotalSeconds
        if ($idle -ge $IdleSeconds) { break }
        Write-Status -State 'idle' -Current '' -Done $done -Failed $failed -Pending 0
        Start-Sleep -Seconds 2
        continue
    }

    foreach ($job in $pending) {
        $name = $job.Name
        $src = Join-Path $job.FullName 'document.docx'
        $outJob = Join-Path $OutDir $name
        New-Item -ItemType Directory -Force -Path $outJob | Out-Null
        $dst = Join-Path $outJob 'document.pdf'
        $res = Join-Path $outJob 'result.json'

        Write-Log ('render {0}' -f $name)
        Write-Status -State 'rendering' -Current $name -Done $done -Failed $failed -Pending $pending.Count

        $argLine = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Src "{1}" -Dst "{2}" -ResultPath "{3}"' -f $renderOne, $src, $dst, $res
        $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $argLine -PassThru -WindowStyle Hidden

        $timedOut = $false
        try {
            Wait-Process -Id $proc.Id -Timeout $DocTimeoutSeconds -ErrorAction Stop
        }
        catch {
            $timedOut = $true
        }

        if ($timedOut) {
            Write-Log ('TIMEOUT {0} after {1}s' -f $name, $DocTimeoutSeconds)
            & taskkill.exe /PID $proc.Id /T /F 2>&1 | Out-Null
        }
        # A killed child can leave Word behind; it must not survive into the next job.
        Get-Process -Name WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500

        if ((Test-Path -LiteralPath $dst) -and ((Get-Item -LiteralPath $dst).Length -gt 0)) {
            (Get-Date).ToString('o') | Set-Content -Path (Join-Path $outJob 'DONE') -Encoding ASCII
            $done++
            Write-Log ('ok   {0}' -f $name)
        }
        else {
            $why = if ($timedOut) { 'timeout' } else { 'no output' }
            $why | Set-Content -Path (Join-Path $outJob 'FAIL') -Encoding ASCII
            $failed++
            Write-Log ('FAIL {0} ({1})' -f $name, $why)
        }
        $lastActivity = Get-Date
    }
}

Write-Status -State 'finished' -Current '' -Done $done -Failed $failed -Pending 0
Write-Log ('agent done; done={0} failed={1} reason={2}' -f $done, $failed, $reason)

if ($NoShutdown -or $reason -eq 'stop-file') {
    Write-Log 'not shutting down'
}
else {
    Write-Log 'shutting down'
    & shutdown.exe /s /t 5 /f /d p:4:1 /c 'oracle batch complete' | Out-Null
}
