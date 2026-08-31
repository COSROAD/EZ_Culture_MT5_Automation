param(
    [string]$CommonFiles = "$env:APPDATA\MetaQuotes\Terminal\Common\Files"
)

$ErrorActionPreference = "Stop"

$OutputFolder = Split-Path $PSScriptRoot -Parent
$ez = Join-Path $CommonFiles "MACD_Trend_Arrow_Signals_v22_EZSquare.csv"
$culture = Join-Path $CommonFiles "MACD_Trend_Arrow_Signals_v22_CultureCapital.csv"
$cultureGenerated = Join-Path $CommonFiles "MACD_Trend_Arrow_Signals_v22_CultureCapital_GeneratedTime.csv"
$out = Join-Path $OutputFolder "MT5_Signal_Data.xlsx"
$tempCulture = Join-Path $env:TEMP "MT5_CultureCapital_Merged.csv"

$legacyHeaders = @(
    "TIME",
    "BROKER",
    "SERVER",
    "SYMBOL",
    "PERIOD",
    "DIRECTION",
    "SCORE",
    "CLASS",
    "PRICE",
    "MA",
    "ICHI",
    "CLOUD",
    "MOMENTUM",
    "MACD_ATR",
    "MACD_ATR_RATIO"
)

function Get-SignalKey {
    param($Row)

    $parts = foreach ($h in $legacyHeaders) {
        [string]$Row.$h
    }

    return ($parts -join [string][char]31)
}

function Build-CultureMergedCsv {
    if (!(Test-Path $culture)) {
        return $null
    }

    $legacyRows = @(Import-Csv -Path $culture -Delimiter ";" -Encoding UTF8)

    $generatedRows = @()
    if (Test-Path $cultureGenerated) {
        $generatedRows = @(Import-Csv -Path $cultureGenerated -Delimiter ";" -Encoding UTF8)
    }

    $generatedQueues = @{}

    foreach ($g in $generatedRows) {
        $key = Get-SignalKey $g

        if (!$generatedQueues.ContainsKey($key)) {
            $generatedQueues[$key] = New-Object System.Collections.Queue
        }

        $generatedQueues[$key].Enqueue($g)
    }

    $merged = New-Object System.Collections.Generic.List[object]

    foreach ($r in $legacyRows) {
        $generatedTime = ""
        $key = Get-SignalKey $r

        if ($generatedQueues.ContainsKey($key) -and $generatedQueues[$key].Count -gt 0) {
            $g = $generatedQueues[$key].Dequeue()
            $generatedTime = [string]$g.SIGNAL_GENERATED_TIME_UTC
        }

        $o = [ordered]@{}

        foreach ($h in $legacyHeaders) {
            $o[$h] = [string]$r.$h
        }

        $o["SIGNAL_GENERATED_TIME_UTC"] = $generatedTime
        $merged.Add([pscustomobject]$o)
    }

    foreach ($g in $generatedRows) {
        $key = Get-SignalKey $g

        if ($generatedQueues.ContainsKey($key) -and $generatedQueues[$key].Count -gt 0) {
            if ([object]::ReferenceEquals($generatedQueues[$key].Peek(), $g)) {
                [void]$generatedQueues[$key].Dequeue()

                $o = [ordered]@{}

                foreach ($h in $legacyHeaders) {
                    $o[$h] = [string]$g.$h
                }

                $o["SIGNAL_GENERATED_TIME_UTC"] = [string]$g.SIGNAL_GENERATED_TIME_UTC
                $merged.Add([pscustomobject]$o)
            }
        }
    }

    $merged | Export-Csv -Path $tempCulture -Delimiter ";" -NoTypeInformation -Encoding UTF8

    return $tempCulture
}

function Import-CsvToSheet {
    param(
        [string]$CsvPath,
        [object]$Workbook,
        [string]$SheetName
    )

    if (!(Test-Path $CsvPath)) {
        return $false
    }

    try {
        $sheet = $Workbook.Worksheets.Item($SheetName)
        $sheet.Cells.Clear() | Out-Null
    }
    catch {
        $sheet = $Workbook.Worksheets.Add()
        $sheet.Name = $SheetName
    }

    $qt = $sheet.QueryTables.Add("TEXT;$CsvPath", $sheet.Range("A1"))
    $qt.TextFileParseType = 1
    $qt.TextFileSemicolonDelimiter = $true
    $qt.TextFileCommaDelimiter = $false
    $qt.TextFilePlatform = 65001
    $qt.AdjustColumnWidth = $true
    $qt.Refresh($false) | Out-Null
    $qt.Delete()

    $sheet.Columns.AutoFit() | Out-Null

    return $true
}

if (!(Test-Path "F:\")) {
    exit 2
}

if (!(Test-Path $OutputFolder)) {
    exit 3
}

if (!(Test-Path $ez) -and !(Test-Path $culture)) {
    exit 4
}

$excel = $null
$wb = $null

try {
    $cultureImport = Build-CultureMergedCsv

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false

    if (Test-Path $out) {
        $wb = $excel.Workbooks.Open($out)
    }
    else {
        $wb = $excel.Workbooks.Add()
    }

    $found = $false

    if (Import-CsvToSheet $ez $wb "EZSquare") {
        $found = $true
    }

    if ($cultureImport -and (Import-CsvToSheet $cultureImport $wb "CultureCapital")) {
        $found = $true
    }

    if (!$found) {
        exit 5
    }

    foreach ($s in @($wb.Worksheets)) {
        if (($s.Name -like "Sheet*") -and $wb.Worksheets.Count -gt 2) {
            $s.Delete()
        }
    }

    if (Test-Path $out) {
        $wb.Save()
    }
    else {
        $wb.SaveAs($out, 51)
    }

    $wb.Close($true)
    $wb = $null
}
finally {
    if ($wb) {
        try { $wb.Close($false) } catch {}
    }

    if ($excel) {
        try { $excel.Quit() } catch {}
        try {
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
        }
        catch {}
    }

    if (Test-Path $tempCulture) {
        try { Remove-Item $tempCulture -Force } catch {}
    }

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}