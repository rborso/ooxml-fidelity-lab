#Requires -Version 5.1
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Harden a Windows 11 VM into a deterministic Office document-rendering oracle.

.DESCRIPTION
    Removes consumer bloat, disables telemetry and update machinery, and pins the
    session, power and printer state that Word's layout depends on.

    Intended for an OFFLINE, snapshotted test VM. Not for a networked machine with
    real users.

    Deliberately does NOT touch things Word needs:
      - Print Spooler   (Word lays out against the default printer's metrics)
      - Windows Installer, COM/DCOM, RPC, .NET, VBScript/WSH
      - The font store
      - The Trusted Location / Protected View policy used by the automation

    Every action is idempotent and logged. Run with -Verify to check state without
    changing anything.

.PARAMETER Verify
    Check only. Changes nothing. Exits non-zero if any required invariant fails.

.PARAMETER SkipApps
    Leave installed Store apps alone.

.PARAMETER SkipTelemetry
    Leave telemetry and consumer-feature policy alone.

.PARAMETER SkipUpdates
    Leave Windows Update services and policy alone.

.PARAMETER SkipSession
    Leave power, lock screen, hibernation and auto-logon alone.

.PARAMETER ConfigureOffice
    Apply Office 2019 settings: Protected View, telemetry tasks, graphics
    acceleration, field-update behaviour. Run as the user that will auto-logon,
    because several of these settings live under HKCU.

.PARAMETER AutoLoginUser
    Optional local account to enable auto-logon for. Requires -AutoLoginPassword.

.PARAMETER AutoLoginPassword
    Optional. NOTE: this is stored in plaintext under HKLM by Windows itself.
    Acceptable only on an isolated, offline VM.

.PARAMETER WorkDir
    Directory the oracle reads and writes. Gets a Defender exclusion and becomes
    the Office Trusted Location. Default C:\work

.PARAMETER LogPath
    Where the transcript and state.json are written. Default C:\oracle-harden

.EXAMPLE
    .\oracle-harden.ps1 -ConfigureOffice

.EXAMPLE
    .\oracle-harden.ps1 -AutoLoginUser oracle -AutoLoginPassword 'S3cret' -ConfigureOffice

.EXAMPLE
    .\oracle-harden.ps1 -Verify
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Verify,
    [switch]$SkipApps,
    [switch]$SkipTelemetry,
    [switch]$SkipUpdates,
    [switch]$SkipSession,
    [switch]$ConfigureOffice,
    [string]$AutoLoginUser,
    [string]$AutoLoginPassword,
    [string]$WorkDir = 'C:\work',
    [string]$LogPath = 'C:\oracle-harden'
)

$ErrorActionPreference = 'Continue'
$script:Changes = [System.Collections.Generic.List[string]]::new()
$script:Failures = [System.Collections.Generic.List[string]]::new()

#region logging
if (-not (Test-Path $LogPath)) { New-Item -ItemType Directory -Path $LogPath -Force | Out-Null }
$logFile = Join-Path $LogPath ("oracle-harden-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Write-Log {
    param([string]$Message, [ValidateSet('green','yellow','red','gray','cyan')][string]$Color = 'gray')
    $line = "{0}  {1}" -f (Get-Date -Format 'HH:mm:ss'), $Message
    Write-Host $line -ForegroundColor $Color
    Add-Content -Path $logFile -Value $line
}

function Write-Section {
    param([string]$Name)
    Write-Log ""
    Write-Log "== $Name ==" 'cyan'
}

function Set-RegValue {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([string]$Path, [string]$Name, $Value, [ValidateSet('DWord','String','QWord','ExpandString')][string]$Type = 'DWord')
    if ($PSCmdlet.ShouldProcess("$Path\$Name", "set to $Value")) {
        try {
            if (-not (Test-Path $Path)) { New-Item -Path $Path -Force | Out-Null }
            New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType $Type -Force -ErrorAction Stop | Out-Null
            $script:Changes.Add("reg $Path\$Name=$Value")
            Write-Log "ok    $Path\$Name = $Value" 'green'
        } catch {
            Write-Log "warn  $Path\$Name : $($_.Exception.Message)" 'yellow'
        }
    }
}

function Set-ServiceState {
    [CmdletBinding(SupportsShouldProcess = $true)]
    param([string]$Name, [ValidateSet('Disabled','Manual','Automatic')][string]$StartupType, [switch]$Stop)
    $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
    if (-not $svc) { Write-Log "skip  service $Name (absent)" 'gray'; return }
    try {
        if ($PSCmdlet.ShouldProcess("service $Name", "set $StartupType")) {
            Set-Service -Name $Name -StartupType $StartupType -ErrorAction Stop
            if ($Stop -and $svc.Status -eq 'Running') { Stop-Service -Name $Name -Force -ErrorAction SilentlyContinue }
            $script:Changes.Add("service $Name=$StartupType")
            Write-Log "ok    service $Name -> $StartupType" 'green'
        }
    } catch {
        # Protected services (WaaSMedicSvc and friends) reject Set-Service.
        $reg = "HKLM:\SYSTEM\CurrentControlSet\Services\$Name"
        if (Test-Path $reg) {
            $start = switch ($StartupType) { 'Disabled' { 4 } 'Manual' { 3 } default { 2 } }
            try {
                Set-ItemProperty -Path $reg -Name Start -Value $start -Force -ErrorAction Stop
                $script:Changes.Add("service-reg $Name=$start")
                Write-Log "reg   service $Name -> Start=$start (protected)" 'yellow'
            } catch {
                Write-Log "warn  service $Name not settable: $($_.Exception.Message)" 'red'
            }
        }
    }
}

function Disable-TaskPath {
    param([string]$TaskPath)
    $tasks = Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue
    if (-not $tasks) { Write-Log "skip  tasks $TaskPath (none)" 'gray'; return }
    foreach ($t in $tasks) {
        try {
            Disable-ScheduledTask -TaskPath $t.TaskPath -TaskName $t.TaskName -ErrorAction Stop | Out-Null
            $script:Changes.Add("task $($t.TaskPath)$($t.TaskName)=disabled")
            Write-Log "ok    task $($t.TaskName) disabled" 'green'
        } catch {
            Write-Log "warn  task $($t.TaskName): $($_.Exception.Message)" 'yellow'
        }
    }
}
function Invoke-PowerCfg {
    param([string[]]$Arguments, [string]$Label)
    $out = & powercfg @Arguments 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Log "ok    power: $Label" 'green'
        $script:Changes.Add("powercfg $($Arguments -join ' ')")
        return $true
    }
    # Aliases vary by build; an unsupported one is a skip, not a failure.
    Write-Log "skip  power: $Label (unsupported on this build)" 'gray'
    return $false
}

function Get-PowerValue {
    param([string]$Sub, [string]$Setting)
    $out = & powercfg /query SCHEME_CURRENT $Sub $Setting 2>$null
    $m = $out | Select-String -Pattern 'Current AC Power Setting Index:\s*(0x[0-9a-fA-F]+)'
    if ($m) { return [Convert]::ToInt32($m.Matches[0].Groups[1].Value, 16) }
    return $null
}
#endregion

# Packages we never remove, whatever else matches.
$ProtectedAppx = @(
    'Microsoft.WindowsStore', 'Microsoft.DesktopAppInstaller', 'Microsoft.SecHealthUI',
    'Microsoft.WindowsTerminal', 'Microsoft.WindowsNotepad', 'Microsoft.Paint'
)
$ProtectedAppxPatterns = @('*VCLibs*', '*NET.Native*', '*UI.Xaml*', '*Services.Store*')

# Store apps to remove. Allowlist only — never blanket-remove.
$AppxRemove = @(
    'Microsoft.549981C3F5F10',            # Cortana
    'Microsoft.BingNews', 'Microsoft.BingWeather', 'Microsoft.BingSearch',
    'Microsoft.GetHelp', 'Microsoft.Getstarted',
    'Microsoft.MicrosoftOfficeHub',       # Office hub stub, not Office itself
    'Microsoft.MicrosoftSolitaireCollection', 'Microsoft.MicrosoftStickyNotes',
    'Microsoft.People', 'Microsoft.PowerAutomateDesktop', 'Microsoft.SkypeApp',
    'Microsoft.Todos', 'Microsoft.WindowsAlarms', 'Microsoft.WindowsCamera',
    'Microsoft.WindowsCommunicationsApps', 'Microsoft.WindowsFeedbackHub',
    'Microsoft.WindowsMaps', 'Microsoft.WindowsSoundRecorder', 'Microsoft.YourPhone',
    'Microsoft.ZuneMusic', 'Microsoft.ZuneVideo', 'MicrosoftTeams',
    'Microsoft.GamingApp', 'Microsoft.Xbox.TCUI', 'Microsoft.XboxApp',
    'Microsoft.XboxGamingOverlay', 'Microsoft.XboxIdentityProvider',
    'Microsoft.XboxSpeechToTextOverlay', 'Clipchamp.Clipchamp',
    'Microsoft.Copilot', 'Microsoft.OutlookForWindows',
    'Microsoft.Windows.DevHome', 'MicrosoftCorporationII.QuickAssist'
)

# Services that must exist and keep running for Word rendering to work.
$MustRemainRunning = @('Spooler', 'EventLog', 'Schedule', 'RpcSs', 'DcomLaunch',
                       'CryptSvc', 'msiserver', 'Themes', 'StateRepository')

if ($Verify) {
    #region verify
    Write-Log "Oracle verification" 'cyan'
    $checks = @(
        @{ Name = 'Print Spooler running (Word uses printer metrics)'
           Test = { (Get-Service Spooler).Status -eq 'Running' } }
        @{ Name = 'Windows Installer available'
           Test = { (Get-Service msiserver).StartType -ne 'Disabled' } }
        @{ Name = 'COM/RPC responding'
           Test = { $null -ne (New-Object -ComObject WScript.Shell) } }
        @{ Name = 'Font store intact (>100 fonts)'
           Test = { (Get-ChildItem "$env:WINDIR\Fonts" -File -ErrorAction SilentlyContinue).Count -gt 100 } }
        @{ Name = 'Telemetry policy set to 0'
           Test = { (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection' -Name AllowTelemetry -ErrorAction SilentlyContinue).AllowTelemetry -eq 0 } }
        @{ Name = 'Windows Update service disabled'
           Test = { (Get-Service wuauserv).StartType -eq 'Disabled' } }
        @{ Name = "Work dir exists ($WorkDir)"
           Test = { Test-Path $WorkDir } }
        @{ Name = 'Fast Startup disabled'
           Test = { (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name HiberbootEnabled -ErrorAction SilentlyContinue).HiberbootEnabled -eq 0 } }
        @{ Name = 'Hibernation disabled (no hiberfil.sys)'
           Test = { -not (Test-Path "$env:SystemDrive\hiberfil.sys") } }
        @{ Name = 'Power plan is High performance'
           Test = { (powercfg /getactivescheme) -match '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c' } }
        @{ Name = 'Display sleep disabled'
           Test = { (Get-PowerValue SUB_VIDEO VIDEOIDLE) -eq 0 } }
        @{ Name = 'System sleep disabled'
           Test = { (Get-PowerValue SUB_SLEEP STANDBYIDLE) -eq 0 } }
        @{ Name = 'Screen saver disabled'
           Test = { (Get-ItemProperty 'HKCU:\Control Panel\Desktop' -Name ScreenSaveActive -ErrorAction SilentlyContinue).ScreenSaveActive -eq '0' } }
        @{ Name = 'No password prompt on wake'
           Test = { $v = Get-PowerValue SUB_NONE CONSOLELOCK; ($null -eq $v) -or ($v -eq 0) } }
    )

    $office = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration' -ErrorAction SilentlyContinue).ProductReleaseIds
    if (-not $office) {
        $winword = Get-ChildItem 'C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE','C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE' -ErrorAction SilentlyContinue
        $office = if ($winword) { 'MSI/perpetual' } else { $null }
    }
    $checks += @{ Name = 'Microsoft Word installed'; Test = { $null -ne $office } }

    $ok = $true
    foreach ($c in $checks) {
        $passed = $false
        try { $passed = [bool](& $c.Test) } catch { $passed = $false }
        if ($passed) { Write-Log ("PASS  {0}" -f $c.Name) 'green' }
        else { Write-Log ("FAIL  {0}" -f $c.Name) 'red'; $script:Failures.Add($c.Name); $ok = $false }
    }
    Write-Log ""
    if ($ok) { Write-Log "All checks passed." 'green'; exit 0 }
    else { Write-Log ("{0} check(s) failed." -f $script:Failures.Count) 'red'; exit 1 }
    #endregion
}

Write-Log "Oracle hardening starting" 'cyan'
Write-Log "Log: $logFile"
Write-Log "WorkDir: $WorkDir"

#region apps
if (-not $SkipApps) {
    Write-Section 'Store apps'

    foreach ($name in $AppxRemove) {
        if ($ProtectedAppx -contains $name) { Write-Log "skip  $name (protected)" 'gray'; continue }
        $skip = $false
        foreach ($p in $ProtectedAppxPatterns) { if ($name -like $p) { $skip = $true } }
        if ($skip) { Write-Log "skip  $name (framework)" 'gray'; continue }

        $pkgs = Get-AppxPackage -AllUsers -Name $name -ErrorAction SilentlyContinue
        if (-not $pkgs) { Write-Log "skip  $name (absent)" 'gray'; continue }
        foreach ($pkg in $pkgs) {
            if ($PSCmdlet.ShouldProcess($name, 'remove appx')) {
                try {
                    Remove-AppxPackage -Package $pkg.PackageFullName -AllUsers -ErrorAction Stop
                    $script:Changes.Add("appx $name")
                    Write-Log "ok    removed $name" 'green'
                } catch { Write-Log "warn  $name : $($_.Exception.Message)" 'yellow' }
            }
        }
    }

    $prov = Get-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue |
            Where-Object { $AppxRemove -contains $_.DisplayName }
    foreach ($p in $prov) {
        try {
            Remove-AppxProvisionedPackage -Online -PackageName $p.PackageName -ErrorAction Stop | Out-Null
            $script:Changes.Add("appx-provisioned $($p.DisplayName)")
            Write-Log "ok    deprovisioned $($p.DisplayName)" 'green'
        } catch { Write-Log "warn  provisioned $($p.DisplayName): $($_.Exception.Message)" 'yellow' }
    }

    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableWindowsConsumerFeatures' 1
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\CloudContent' 'DisableConsumerAccountStateContent' 1
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager' 'SilentInstalledAppsEnabled' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager' 'SystemPaneSuggestionsEnabled' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager' 'SubscribedContent-338388Enabled' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\ContentDeliveryManager' 'SubscribedContent-338389Enabled' 0
}
#endregion

#region telemetry
if (-not $SkipTelemetry) {
    Write-Section 'Telemetry and consumer features'

    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection' 'AllowTelemetry' 0
    Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection' 'AllowTelemetry' 0
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection' 'DoNotShowFeedbackNotifications' 1
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Siuf\Rules' 'NumberOfSIUFInPeriod' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\AdvertisingInfo' 'Enabled' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Privacy' 'TailoredExperiencesWithDiagnosticDataEnabled' 0
    Set-RegValue 'HKLM:\SOFTWARE\Microsoft\SQMClient\Windows' 'CEIPEnable' 0
    Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Windows\Windows Error Reporting' 'Disabled' 1

    # Copilot / Recall / Widgets / web search in Start
    Set-RegValue 'HKCU:\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot' 'TurnOffWindowsCopilot' 1
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot' 'TurnOffWindowsCopilot' 1
    Set-RegValue 'HKCU:\SOFTWARE\Policies\Microsoft\Windows\WindowsAI' 'DisableAIDataAnalysis' 1
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced' 'TaskbarDa' 0
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Dsh' 'AllowNewsAndInterests' 0
    Set-RegValue 'HKCU:\SOFTWARE\Policies\Microsoft\Windows\Explorer' 'DisableSearchBoxSuggestions' 1
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search' 'DisableWebSearch' 1
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search' 'ConnectedSearchUseWeb' 0

    Set-ServiceState 'DiagTrack'  Disabled -Stop
    Set-ServiceState 'dmwappushservice' Disabled -Stop
    Set-ServiceState 'WerSvc'     Disabled -Stop

    Disable-TaskPath '\Microsoft\Windows\Application Experience\'
    Disable-TaskPath '\Microsoft\Windows\Customer Experience Improvement Program\'
    Disable-TaskPath '\Microsoft\Windows\Feedback\Siuf\'
    Disable-TaskPath '\Microsoft\Windows\Windows Error Reporting\'
    Disable-TaskPath '\Microsoft\Windows\CloudExperienceHost\'
    Disable-TaskPath '\Microsoft\Windows\SettingSync\'
    Disable-TaskPath '\Microsoft\Windows\Speech\'
    Disable-TaskPath '\Microsoft\Windows\Maps\'
}
#endregion

#region updates
if (-not $SkipUpdates) {
    Write-Section 'Windows Update'

    # The VM is offline; this is belt-and-braces so a stray network adapter
    # cannot change the image between snapshots.
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' 'NoAutoUpdate' 1
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' 'AUOptions' 2
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization' 'DODownloadMode' 0

    Set-ServiceState 'wuauserv'    Disabled -Stop
    Set-ServiceState 'WaaSMedicSvc' Disabled
    Set-ServiceState 'UsoSvc'      Disabled -Stop
    Set-ServiceState 'DoSvc'       Disabled -Stop
    Set-ServiceState 'WSearch'     Disabled -Stop
    Set-ServiceState 'SysMain'     Disabled -Stop
    Set-ServiceState 'MapsBroker'  Disabled -Stop
    Set-ServiceState 'RetailDemo'  Disabled -Stop
    Set-ServiceState 'RemoteRegistry' Disabled -Stop
    Set-ServiceState 'lfsvc'       Disabled -Stop
    Set-ServiceState 'XblAuthManager' Disabled -Stop
    Set-ServiceState 'XblGameSave' Disabled -Stop
    Set-ServiceState 'XboxGipSvc'  Disabled -Stop
    Set-ServiceState 'XboxNetApiSvc' Disabled -Stop
    Set-ServiceState 'Fax'         Disabled -Stop

    Disable-TaskPath '\Microsoft\Windows\UpdateOrchestrator\'
    Disable-TaskPath '\Microsoft\Windows\WindowsUpdate\'
}
#endregion

#region determinism
Write-Section 'Determinism: power, session, filesystem'

# Fast Startup is the one that actually bites: with it enabled, "shutdown" is a
# partial hibernate and the next boot inherits state. Two independent switches,
# because either can be re-enabled on its own.
Invoke-PowerCfg @('/h', 'off') 'hibernation off (also removes hiberfil.sys)'
Set-RegValue 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' 'HiberbootEnabled' 0
Set-RegValue 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\PowerThrottling' 'PowerThrottlingOff' 1

# Power saver -> High performance, and no idle transitions of any kind.
Invoke-PowerCfg @('/setactive', 'SCHEME_MIN') 'power plan = High performance'
Invoke-PowerCfg @('/change', 'standby-timeout-ac', '0')  'sleep timeout 0 (AC)'
Invoke-PowerCfg @('/change', 'standby-timeout-dc', '0')  'sleep timeout 0 (DC)'
Invoke-PowerCfg @('/change', 'hibernate-timeout-ac', '0') 'hibernate timeout 0'
Invoke-PowerCfg @('/change', 'disk-timeout-ac', '0')     'disk timeout 0'
Invoke-PowerCfg @('/change', 'monitor-timeout-ac', '0')  'display timeout 0 (AC)'
Invoke-PowerCfg @('/change', 'monitor-timeout-dc', '0')  'display timeout 0 (DC)'

# Never prompt for a password on wake — a locked session can stall UI automation.
Invoke-PowerCfg @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_NONE', 'CONSOLELOCK', '0') 'no password on wake'
# Keep the CPU at a fixed state so timing is not frequency-dependent.
Invoke-PowerCfg @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_PROCESSOR', 'PROCTHROTTLEMIN', '100') 'CPU minimum state 100%'
Invoke-PowerCfg @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_PCIEXPRESS', 'ASPM', '0') 'PCIe power management off'
Invoke-PowerCfg @('/setacvalueindex', 'SCHEME_CURRENT',
    '2a737441-1930-4402-8d77-b2bebba308a3', '48e6b7a6-50f5-4782-a5d4-53bb8f07e226', '0') 'USB selective suspend off'
# Windows 11 24H2 "Energy Saver" is separate from the power plan and can throttle.
Invoke-PowerCfg @('/setacvalueindex', 'SCHEME_CURRENT', 'SUB_ENERGYSAVER', 'ESBATTTHRESHOLD', '0') 'energy saver off'
Invoke-PowerCfg @('/setactive', 'SCHEME_CURRENT') 'apply power settings'

if (-not (Test-Path $WorkDir)) { New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null }
$excl = (Get-MpPreference).ExclusionPath
if ($excl -notcontains $WorkDir) {
    Add-MpPreference -ExclusionPath $WorkDir -ErrorAction SilentlyContinue
    Write-Log "ok    Defender exclusion: $WorkDir" 'green'
} else { Write-Log "skip  Defender exclusion (present)" 'gray' }
Add-MpPreference -ExclusionProcess 'WINWORD.EXE' -ErrorAction SilentlyContinue

# Word must never be blocked by a "file from another computer" mark.
Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Office\16.0\Word\Security\Trusted Locations\Location1' 'Path' "$WorkDir\" 'String'
Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Office\16.0\Word\Security\Trusted Locations\Location1' 'AllowSubfolders' 1
Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Office\16.0\Word\Security\Trusted Locations\Location1' 'Description' 'fidelity-lab' 'String'
Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Word\Security\ProtectedView' 'DisableInternetFilesInPV' 1
Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Word\Security\ProtectedView' 'DisableUnsafeLocationsInPV' 1
Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Word\Security\ProtectedView' 'DisableAttachmentsInPV' 1

if (-not $SkipSession) {
    # Screen saver: policy keys plus the real per-user keys, because the policy
    # alone does not clear an already-configured saver.
    Set-RegValue 'HKCU:\SOFTWARE\Policies\Microsoft\Windows\Control Panel\Desktop' 'ScreenSaveActive' '0' 'String'
    Set-RegValue 'HKCU:\SOFTWARE\Policies\Microsoft\Windows\Control Panel\Desktop' 'ScreenSaverIsSecure' '0' 'String'
    Set-RegValue 'HKCU:\Control Panel\Desktop' 'ScreenSaveActive' '0' 'String'
    Set-RegValue 'HKCU:\Control Panel\Desktop' 'ScreenSaveTimeOut' '0' 'String'
    Set-RegValue 'HKCU:\Control Panel\Desktop' 'ScreenSaverIsSecure' '0' 'String'
    Set-RegValue 'HKCU:\Control Panel\Desktop' 'SCRNSAVE.EXE' '' 'String'

    # Lock screen and automatic lock
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization' 'NoLockScreen' 1
    Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' 'InactivityTimeoutSecs' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'EnableDynamicLock' 0

    # Best-performance visuals: less repaint noise during automation.
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects' 'VisualFXSetting' 2

    if ($AutoLoginUser -and $AutoLoginPassword) {
        Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'AutoAdminLogon' '1' 'String'
        Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'DefaultUserName' $AutoLoginUser 'String'
        Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'DefaultPassword' $AutoLoginPassword 'String'
        Set-RegValue 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' 'DefaultDomainName' $env:COMPUTERNAME 'String'
        Write-Log "warn  auto-logon password stored in plaintext (offline VM only)" 'yellow'
    } else {
        Write-Log "skip  auto-logon (no credentials supplied)" 'gray'
    }
}

# Invariant check, so a typo cannot silently break the oracle.
foreach ($svc in $MustRemainRunning) {
    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if ($s -and $s.StartType -eq 'Disabled') {
        Write-Log "FIX   $svc was disabled — restoring to Manual" 'red'
        Set-Service -Name $svc -StartupType Manual -ErrorAction SilentlyContinue
        $script:Failures.Add("restored $svc")
    }
}
#endregion

#region office
if ($ConfigureOffice) {
    Write-Section 'Office 2019'

    $c2r = 'HKLM:\SOFTWARE\Microsoft\Office\ClickToRun\Configuration'
    if (Test-Path $c2r) {
        Set-RegValue $c2r 'UpdatesEnabled' 'False' 'String'
        Set-RegValue $c2r 'UpdateChannel' '' 'String'
    } else {
        Write-Log "skip  ClickToRun config (perpetual/MSI install)" 'gray'
    }

    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Common\Graphics' 'DisableHardwareAcceleration' 1
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Word\Options' 'UpdateFieldsBeforePrint' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Word\Options' 'UpdateLinksAtOpen' 0
    Set-RegValue 'HKCU:\SOFTWARE\Microsoft\Office\16.0\Common\General' 'ShownFirstRunOptin' 1
    Set-RegValue 'HKCU:\SOFTWARE\Policies\Microsoft\Office\16.0\Common' 'QMEnable' 0
    Set-RegValue 'HKCU:\SOFTWARE\Policies\Microsoft\Office\16.0\Common' 'SendCustomerData' 0
    Set-RegValue 'HKLM:\SOFTWARE\Policies\Microsoft\Office\16.0\Common' 'SendCustomerData' 0

    Disable-TaskPath '\Microsoft\Office\'
}
#endregion

#region state
Write-Section 'State snapshot'

$os = Get-CimInstance Win32_OperatingSystem
$nt = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$officeVersion = $null
$winword = Get-ChildItem 'C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE',
                           'C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE' -ErrorAction SilentlyContinue
if ($winword) { $officeVersion = $winword[0].VersionInfo.FileVersion }

$state = [ordered]@{
    capturedAt      = (Get-Date).ToString('o')
    os              = $os.Caption
    displayVersion  = $nt.DisplayVersion
    build           = $nt.CurrentBuild
    ubr             = $nt.UBR
    wordVersion     = $officeVersion
    fontFiles       = (Get-ChildItem "$env:WINDIR\Fonts" -File -ErrorAction SilentlyContinue).Count
    workDir         = $WorkDir
    changes         = $script:Changes
    warnings        = $script:Failures
    hostName        = $env:COMPUTERNAME
}
$statePath = Join-Path $LogPath 'state.json'
$state | ConvertTo-Json -Depth 5 | Set-Content -Path $statePath -Encoding UTF8
Write-Log "wrote $statePath" 'green'

Write-Log ""
Write-Log ("Applied {0} change(s); {1} warning(s)." -f $script:Changes.Count, $script:Failures.Count) 'cyan'
Write-Log "Never clone this VM across parallel workers on one activation." 'yellow'
Write-Log "Snapshot, record the image hash, then remove the network adapter." 'yellow'
#endregion
