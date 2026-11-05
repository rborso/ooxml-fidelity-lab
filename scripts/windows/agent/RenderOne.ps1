#Requires -Version 5.1
<#
.SYNOPSIS
    Render a single DOCX to PDF with Microsoft Word.

.DESCRIPTION
    Runs in its own process so the parent can enforce a timeout by killing it.
    Word COM has no cancellation: a hung document is a hung process.

    Invoked by OracleAgent.ps1. Do not run Word any other way on this VM.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Src,
    [Parameter(Mandatory = $true)][string]$Dst,
    [string]$ResultPath
)

$ErrorActionPreference = 'Stop'
$started = Get-Date
$word = $null
$doc = $null
$status = 'ok'
$errorText = $null
$applied = @()

function Get-WordVersion {
    $k = 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration'
    return (Get-ItemProperty -Path $k -Name VersionToReport -ErrorAction SilentlyContinue).VersionToReport
}

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    # Field and link updates make output depend on the clock. Each is set in its
    # own guard: Word's Options surface differs by build, and a missing property
    # must not abort an otherwise good render.
    $applied = @()
    foreach ($name in 'UpdateFieldsAtPrint', 'UpdateLinksAtOpen', 'UpdateLinksAtPrint') {
        try {
            $word.Options.$name = $false
            $applied += $name
        } catch { }
    }

    # FileName, ConfirmConversions, ReadOnly, AddToRecentFiles
    $doc = $word.Documents.Open($Src, $false, $true, $false)

    # OutputFileName, ExportFormat(17=PDF), OpenAfterExport,
    # OptimizeFor(0=print), Range(0=all), From, To, Item(0=content),
    # IncludeDocProps, KeepIRM, CreateBookmarks(0=none), DocStructureTags,
    # BitmapMissingFonts, UseISO19005_1
    $doc.ExportAsFixedFormat($Dst, 17, $false, 0, 0, 1, 1, 0, $true, $true, 0, $true, $true, $false)
}
catch {
    $status = 'error'
    $errorText = $_.Exception.Message
}
finally {
    if ($doc) { try { $doc.Close(0) } catch { } }
    if ($word) { try { $word.Quit() } catch { } }
    if ($doc) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) }
    if ($word) { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
}

if ($ResultPath) {
    $result = [ordered]@{
        src         = $Src
        dst         = $Dst
        status      = $status
        error       = $errorText
        options     = $applied
        pdfBytes    = if (Test-Path -LiteralPath $Dst) { (Get-Item -LiteralPath $Dst).Length } else { 0 }
        seconds     = [math]::Round(((Get-Date) - $started).TotalSeconds, 2)
        wordVersion = (Get-WordVersion)
        machine     = $env:COMPUTERNAME
        startedAt   = $started.ToString('o')
    }
    ($result | ConvertTo-Json) | Set-Content -Path $ResultPath -Encoding UTF8
}

if ($status -ne 'ok') { exit 1 }
