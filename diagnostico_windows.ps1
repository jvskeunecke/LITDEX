# Read-only Windows/GPU diagnostics for VIDEO_TDR_FAILURE and nvlddmkm.sys.
# Does not modify drivers, registry, power settings, or user files.
$ErrorActionPreference = 'Continue'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$outDir = Join-Path $PSScriptRoot "diagnostico_$stamp"
try {
    New-Item -ItemType Directory -Path $outDir -Force -ErrorAction Stop | Out-Null
} catch {
    Write-Error "Cannot create report folder '$outDir'. Run from a writable folder. $($_.Exception.Message)"
    exit 1
}
$out = Join-Path $outDir 'resumo.txt'
"LitDex / Windows diagnostic - $((Get-Date).ToString('s'))" | Set-Content -LiteralPath $out -Encoding UTF8
"Privacy note: review this report before sharing. It can include device names and local paths." | Add-Content -LiteralPath $out -Encoding UTF8
function Add-Section([string]$Title, [string]$Body) {
    "`r`n===== $Title =====`r`n$Body" | Add-Content -LiteralPath $out -Encoding UTF8
}

Add-Section 'PowerShell / Windows' ((Get-ComputerInfo -ErrorAction SilentlyContinue | Select-Object WindowsProductName,WindowsVersion,OsBuildNumber,OsArchitecture,CsTotalPhysicalMemory | Format-List | Out-String))
Add-Section 'GPU / driver' ((Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object Name,DriverVersion,DriverDate,VideoProcessor,AdapterRAM,Status,PNPDeviceID | Format-List | Out-String))
Add-Section 'Display devices' ((Get-PnpDevice -Class Display -ErrorAction SilentlyContinue | Format-List Status,Class,FriendlyName,InstanceId | Out-String))

$since = (Get-Date).AddDays(-14)
$events = @()
try {
    $events = Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = $since; Level = 1,2,3 } -MaxEvents 800 -ErrorAction Stop |
        Where-Object { $_.ProviderName -match 'Display|nvlddmkm|WHEA|BugCheck|Kernel-Power|Windows Error Reporting' -or $_.Message -match 'VIDEO_TDR_FAILURE|nvlddmkm|0x00000116|display driver' } |
        Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message
} catch {
    $events = @("Could not read System event log: $($_.Exception.Message)")
}
Add-Section 'Relevant system events (last 14 days)' (($events | Format-List | Out-String))

$dumpDir = Join-Path $env:SystemRoot 'Minidump'
$dumps = @()
if (Test-Path -LiteralPath $dumpDir) {
    $dumps = Get-ChildItem -LiteralPath $dumpDir -Filter '*.dmp' -ErrorAction SilentlyContinue | Select-Object Name,Length,LastWriteTime
}
Add-Section 'Minidump files (names/dates only)' (($dumps | Format-Table -AutoSize | Out-String))

$dxdiagPath = Join-Path $outDir 'dxdiag.txt'
try {
    $proc = Start-Process -FilePath 'dxdiag.exe' -ArgumentList @('/whql:off', '/t', "`"$dxdiagPath`"") -Wait -PassThru -ErrorAction Stop
    if ($proc.ExitCode -ne 0) { Add-Section 'DxDiag' "dxdiag returned exit code $($proc.ExitCode)." }
} catch {
    Add-Section 'DxDiag' "Could not run dxdiag: $($_.Exception.Message)"
}

Add-Content -LiteralPath $out -Encoding UTF8 -Value "`r`nReport folder: $outDir`r`nShare resumo.txt and dxdiag.txt if present. Do not share .dmp files unless specifically needed; they can contain memory data."
Write-Host "Diagnostics complete. Report: $outDir" -ForegroundColor Green
Write-Host 'Read-only script: it does not install or modify drivers.'
