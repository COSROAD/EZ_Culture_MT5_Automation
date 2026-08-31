$ErrorActionPreference = "Stop"

$Root       = "F:\마켓 프리존\EZ_컬쳐캐피탈-Auto"
$Common     = "$env:APPDATA\MetaQuotes\Terminal\Common\Files"
$AutoSync   = Join-Path $Root "AutoSync"

$V4         = Join-Path $AutoSync "MT5_CSV_to_FDrive_XLSX_V4.ps1"
$LocalXlsx  = Join-Path $Root "MT5_Signal_Data.xlsx"

$EZ         = Join-Path $Common "MACD_Trend_Arrow_Signals_v22_EZSquare.csv"
$Culture    = Join-Path $Common "MACD_Trend_Arrow_Signals_v22_CultureCapital.csv"
$Generated  = Join-Path $Common "MACD_Trend_Arrow_Signals_v22_CultureCapital_GeneratedTime.csv"

$DriveDir   = "G:\내 드라이브\MT5_Auto"
$DriveXlsx  = Join-Path $DriveDir "MT5_Signal_Data.xlsx"

try {
    if(!(Test-Path -LiteralPath $V4))        { throw "V4_NOT_FOUND" }
    if(!(Test-Path -LiteralPath $EZ))        { throw "EZ_SIGNAL_CSV_NOT_FOUND" }
    if(!(Test-Path -LiteralPath $Culture))   { throw "CULTURE_SIGNAL_CSV_NOT_FOUND" }
    if(!(Test-Path -LiteralPath $Generated)) { throw "GENERATEDTIME_CSV_NOT_FOUND" }
    if(!(Test-Path -LiteralPath $DriveDir))  { throw "DRIVE_DESTINATION_NOT_FOUND" }

    $beforeExists = Test-Path -LiteralPath $LocalXlsx
    $beforeTime = if($beforeExists) {
        (Get-Item -LiteralPath $LocalXlsx).LastWriteTimeUtc
    } else {
        [datetime]::MinValue
    }

    $proc = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", "`"$V4`""
        ) `
        -Wait `
        -PassThru `
        -WindowStyle Hidden

    if($proc.ExitCode -ne 0) {
        throw "V4_EXIT_CODE_$($proc.ExitCode)"
    }

    if(!(Test-Path -LiteralPath $LocalXlsx)) {
        throw "LOCAL_XLSX_NOT_CREATED"
    }

    $local = Get-Item -LiteralPath $LocalXlsx

    if($local.LastWriteTimeUtc -le $beforeTime) {
        throw "LOCAL_XLSX_NOT_UPDATED"
    }

    $localLength = $local.Length

    Copy-Item -LiteralPath $LocalXlsx -Destination $DriveXlsx -Force

    if(!(Test-Path -LiteralPath $DriveXlsx)) {
        throw "DRIVE_COPY_NOT_FOUND"
    }

    $drive = Get-Item -LiteralPath $DriveXlsx

    if($drive.Length -ne $localLength) {
        throw "DRIVE_COPY_SIZE_MISMATCH"
    }

    Write-Output "SIGNAL_ORCHESTRATOR=PASS"
    Write-Output "V4_EXIT_CODE=0"
    Write-Output "LOCAL_XLSX=$LocalXlsx"
    Write-Output "LOCAL_MODIFIED_UTC=$($local.LastWriteTimeUtc.ToString('yyyy-MM-dd HH:mm:ss.fff'))"
    Write-Output "LOCAL_SIZE=$($local.Length)"
    Write-Output "DRIVE_XLSX=$DriveXlsx"
    Write-Output "DRIVE_MODIFIED_UTC=$($drive.LastWriteTimeUtc.ToString('yyyy-MM-dd HH:mm:ss.fff'))"
    Write-Output "DRIVE_SIZE=$($drive.Length)"
    exit 0
}
catch {
    Write-Output "SIGNAL_ORCHESTRATOR=FAIL"
    Write-Output "ERROR=$($_.Exception.Message)"
    exit 20
}
