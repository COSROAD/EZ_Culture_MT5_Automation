param(
    [string]$ProjectRoot = "F:\마켓 프리존\EZ_컬쳐캐피탈-Auto",
    [string]$CommonFiles = "$env:APPDATA\MetaQuotes\Terminal\Common\Files",
    [int]$LookbackDays = 7
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RawArchive = Join-Path $ProjectRoot "04_CSV_기록"
$AutoSyncDir = Join-Path $ProjectRoot "AutoSync"
$OutputXlsx = Join-Path $ProjectRoot "MT5_Market_Data.xlsx"
$TempXlsx = Join-Path $ProjectRoot "MT5_Market_Data.tmp.xlsx"
$RunLog = Join-Path $AutoSyncDir "MT5_MarketData_AutoSync.log"
$ErrorLog = Join-Path $AutoSyncDir "MT5_MarketData_Error.log"
$HealthLog = Join-Path $AutoSyncDir "MT5_MarketData_Health.log"

function Write-Log {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $RunLog -Value $line -Encoding UTF8
    Write-Host $line
}

function Write-ErrorLog {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -LiteralPath $ErrorLog -Value $line -Encoding UTF8
    Write-Host $line -ForegroundColor Red
}

function Write-Health {
    param([string]$Broker, [string]$Status, [string]$Detail)
    $line = "{0},BROKER={1},STATUS={2},DETAIL={3}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Broker, $Status, $Detail
    Add-Content -LiteralPath $HealthLog -Value $line -Encoding UTF8
    Write-Host $line
}

function Assert-ExistingDirectory {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "$Label folder not found: $Path"
    }
}

function Copy-StableRawFile {
    param([System.IO.FileInfo]$Source, [string]$Destination)

    $needsCopy = $true
    if (Test-Path -LiteralPath $Destination -PathType Leaf) {
        $dst = Get-Item -LiteralPath $Destination
        if ($dst.Length -eq $Source.Length -and $dst.LastWriteTimeUtc -ge $Source.LastWriteTimeUtc) {
            $needsCopy = $false
        }
    }

    if (-not $needsCopy) { return $false }

    $tmp = "$Destination.copytmp"
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }

        $before = Get-Item -LiteralPath $Source.FullName
        Copy-Item -LiteralPath $Source.FullName -Destination $tmp -Force
        $after = Get-Item -LiteralPath $Source.FullName
        $copied = Get-Item -LiteralPath $tmp

        if ($before.Length -eq $after.Length -and $copied.Length -eq $after.Length) {
            Move-Item -LiteralPath $tmp -Destination $Destination -Force
            (Get-Item -LiteralPath $Destination).LastWriteTimeUtc = $after.LastWriteTimeUtc
            return $true
        }

        Start-Sleep -Milliseconds 500
    }

    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
    throw "Raw file changed repeatedly during copy: $($Source.FullName)"
}

function Get-ColumnName {
    param([int]$Index)
    $name = ""
    $n = $Index
    while ($n -gt 0) {
        $n--
        $name = [char](65 + ($n % 26)) + $name
        $n = [math]::Floor($n / 26)
    }
    return $name
}

function Xml-Escape {
    param([string]$Text)
    if ($null -eq $Text) { return "" }
    return [System.Security.SecurityElement]::Escape($Text)
}

function Write-ZipTextEntry {
    param(
        [System.IO.Compression.ZipArchive]$Zip,
        [string]$EntryName,
        [string]$Text
    )
    $entry = $Zip.CreateEntry($EntryName, [System.IO.Compression.CompressionLevel]::Optimal)
    $stream = $entry.Open()
    try {
        $writer = New-Object System.IO.StreamWriter($stream, (New-Object System.Text.UTF8Encoding($false)))
        try { $writer.Write($Text) } finally { $writer.Dispose() }
    } finally {
        $stream.Dispose()
    }
}

function Write-MarketDataXlsx {
    param(
        [string]$Path,
        [string[]]$Headers,
        [object[]]$Rows
    )

    if ($Rows.Count + 1 -gt 1048576) {
        throw "Excel row limit exceeded: $($Rows.Count + 1)"
    }

    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem

    if (Test-Path -LiteralPath $Path) { Remove-Item -LiteralPath $Path -Force }
    $fs = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    try {
        $zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Create, $true)
        try {
            $contentTypes = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
'@
            $rootRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
'@
            $workbook = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="MarketData_5m" sheetId="1" r:id="rId1"/></sheets>
</workbook>
'@
            $workbookRels = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
'@
            $styles = @'
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
'@

            Write-ZipTextEntry $zip "[Content_Types].xml" $contentTypes
            Write-ZipTextEntry $zip "_rels/.rels" $rootRels
            Write-ZipTextEntry $zip "xl/workbook.xml" $workbook
            Write-ZipTextEntry $zip "xl/_rels/workbook.xml.rels" $workbookRels
            Write-ZipTextEntry $zip "xl/styles.xml" $styles

            $sheetEntry = $zip.CreateEntry("xl/worksheets/sheet1.xml", [System.IO.Compression.CompressionLevel]::Optimal)
            $sheetStream = $sheetEntry.Open()
            try {
                $writer = New-Object System.IO.StreamWriter($sheetStream, (New-Object System.Text.UTF8Encoding($false)))
                try {
                    $writer.Write('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')
                    $writer.Write('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><sheetData>')

                    $writer.Write('<row r="1">')
                    for ($c = 0; $c -lt $Headers.Count; $c++) {
                        $cellRef = "$(Get-ColumnName ($c + 1))1"
                        $writer.Write('<c r="' + $cellRef + '" t="inlineStr" s="1"><is><t>' + (Xml-Escape $Headers[$c]) + '</t></is></c>')
                    }
                    $writer.Write('</row>')

                    $rowNum = 2
                    foreach ($row in $Rows) {
                        $writer.Write('<row r="' + $rowNum + '">')
                        for ($c = 0; $c -lt $Headers.Count; $c++) {
                            $header = $Headers[$c]
                            $value = $row.$header
                            $cellRef = "$(Get-ColumnName ($c + 1))$rowNum"

                            if ($header -in @("TIME_UTC", "TIME_KST", "BROKER", "SERVER", "SYMBOL")) {
                                $writer.Write('<c r="' + $cellRef + '" t="inlineStr"><is><t>' + (Xml-Escape ([string]$value)) + '</t></is></c>')
                            } else {
                                if ($null -eq $value -or [string]::IsNullOrWhiteSpace([string]$value)) { $value = 0 }
                                $numeric = [Convert]::ToString($value, [System.Globalization.CultureInfo]::InvariantCulture)
                                $writer.Write('<c r="' + $cellRef + '"><v>' + $numeric + '</v></c>')
                            }
                        }
                        $writer.Write('</row>')
                        $rowNum++
                    }

                    $writer.Write('</sheetData><autoFilter ref="A1:X' + ($Rows.Count + 1) + '"/></worksheet>')
                } finally { $writer.Dispose() }
            } finally { $sheetStream.Dispose() }
        } finally { $zip.Dispose() }
    } finally { $fs.Dispose() }
}

function Test-MarketDataXlsx {
    param(
        [string]$Path,
        [string[]]$ExpectedHeaders
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    if ((Get-Item -LiteralPath $Path).Length -le 0) { return $false }
    if ($ExpectedHeaders.Count -ne 24) { return $false }

    Add-Type -AssemblyName System.IO.Compression
    $fs = [System.IO.File]::OpenRead($Path)
    try {
        $zip = New-Object System.IO.Compression.ZipArchive($fs, [System.IO.Compression.ZipArchiveMode]::Read)
        try {
            $sheet = $zip.GetEntry("xl/worksheets/sheet1.xml")
            $workbook = $zip.GetEntry("xl/workbook.xml")
            if ($null -eq $sheet -or $null -eq $workbook) { return $false }

            $srWb = New-Object System.IO.StreamReader($workbook.Open())
            try {
                $wbXml = $srWb.ReadToEnd()
                if ($wbXml -notmatch 'sheet name="MarketData_5m"') { return $false }
            } finally { $srWb.Dispose() }

            $sr = New-Object System.IO.StreamReader($sheet.Open())
            try {
                [xml]$xmlDoc = $sr.ReadToEnd()
            } finally { $sr.Dispose() }

            $ns = New-Object System.Xml.XmlNamespaceManager($xmlDoc.NameTable)
            $ns.AddNamespace("x", "http://schemas.openxmlformats.org/spreadsheetml/2006/main")

            $rows = $xmlDoc.SelectNodes("//x:sheetData/x:row", $ns)
            if ($null -eq $rows -or $rows.Count -lt 2) { return $false }

            $headerCells = $rows[0].SelectNodes("x:c", $ns)
            if ($headerCells.Count -ne 24) { return $false }

            $actualHeaders = @()
            foreach ($cell in $headerCells) {
                $t = $cell.SelectSingleNode("x:is/x:t", $ns)
                $actualHeaders += if ($null -eq $t) { "" } else { [string]$t.InnerText }
            }

            for ($i = 0; $i -lt $ExpectedHeaders.Count; $i++) {
                if ($actualHeaders[$i] -ne $ExpectedHeaders[$i]) { return $false }
            }

            $dataCells = $rows[1].SelectNodes("x:c", $ns)
            if ($dataCells.Count -lt 24) { return $false }

            function Get-InlineCellText([System.Xml.XmlElement]$cell) {
                $t = $cell.SelectSingleNode("x:is/x:t", $ns)
                if ($null -ne $t) { return [string]$t.InnerText }
                $v = $cell.SelectSingleNode("x:v", $ns)
                if ($null -ne $v) { return [string]$v.InnerText }
                return ""
            }

            $timeUtc = Get-InlineCellText $dataCells[0]
            $broker = Get-InlineCellText $dataCells[2]
            $server = Get-InlineCellText $dataCells[3]
            $symbol = Get-InlineCellText $dataCells[4]

            $parsedUtc = [DateTime]::MinValue
            if (-not [DateTime]::TryParseExact(
                $timeUtc,
                "yyyy-MM-dd HH:mm:ss",
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::AssumeUniversal,
                [ref]$parsedUtc
            )) { return $false }

            if ([string]::IsNullOrWhiteSpace($broker)) { return $false }
            if ([string]::IsNullOrWhiteSpace($server)) { return $false }
            if ([string]::IsNullOrWhiteSpace($symbol)) { return $false }
        } finally { $zip.Dispose() }
    } finally { $fs.Dispose() }

    return $true
}

function Replace-LocalFileSafely {
    param([string]$TempPath, [string]$FinalPath)
    if (Test-Path -LiteralPath $FinalPath) {
        $backup = "$FinalPath.replacebak"
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
        [System.IO.File]::Replace($TempPath, $FinalPath, $backup, $true)
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
    } else {
        Move-Item -LiteralPath $TempPath -Destination $FinalPath
    }
}

try {
    Assert-ExistingDirectory $ProjectRoot "ProjectRoot"
    Assert-ExistingDirectory $CommonFiles "CommonFiles"
    Assert-ExistingDirectory $RawArchive "RawArchive"
    Assert-ExistingDirectory $AutoSyncDir "AutoSync"

    Write-Log "START Market Data processing. LookbackDays=$LookbackDays"

    $sourceRaw = Get-ChildItem -LiteralPath $CommonFiles -File -ErrorAction Stop |
        Where-Object { $_.Name -match '^MarketDataCollector_(EZ|Culture)_\d{8}\.csv$' }

    foreach ($src in $sourceRaw) {
        $dest = Join-Path $RawArchive $src.Name
        if (Copy-StableRawFile $src $dest) {
            Write-Log "RAW COPIED: $($src.Name) -> $dest"
        }
    }

    $cutoffDate = (Get-Date).Date.AddDays(-1 * [math]::Max(0, $LookbackDays - 1))
    $rawFiles = Get-ChildItem -LiteralPath $RawArchive -File |
        Where-Object {
            if ($_.Name -match '^MarketDataCollector_(EZ|Culture)_(\d{8})\.csv$') {
                try {
                    $fileDate = [DateTime]::ParseExact($Matches[2], "yyyyMMdd", [System.Globalization.CultureInfo]::InvariantCulture)
                    return $fileDate -ge $cutoffDate
                } catch { return $false }
            }
            return $false
        } | Sort-Object Name

    if ($rawFiles.Count -eq 0) { throw "No V3 raw CSV found for the requested lookback window." }

    $groups = @{}
    $brokerLatest = @{}
    [Int64]$rawSequence = 0

    foreach ($file in $rawFiles) {
        Write-Log "READ RAW: $($file.FullName)"
        foreach ($r in (Import-Csv -LiteralPath $file.FullName)) {
            $rawSequence++
            if ([string]::IsNullOrWhiteSpace($r.SERVER_TIME_MSC) -or [string]::IsNullOrWhiteSpace($r.BROKER) -or [string]::IsNullOrWhiteSpace($r.SERVER) -or [string]::IsNullOrWhiteSpace($r.SYMBOL)) {
                Write-ErrorLog "SKIP malformed row in $($file.Name): missing key column."
                continue
            }

            try {
                $msc = [Int64]$r.SERVER_TIME_MSC
                $utc = [DateTimeOffset]::FromUnixTimeMilliseconds($msc).UtcDateTime
                $bucketMinute = [math]::Floor($utc.Minute / 5) * 5
                $bucketUtc = [DateTime]::new($utc.Year, $utc.Month, $utc.Day, $utc.Hour, [int]$bucketMinute, 0, [DateTimeKind]::Utc)
                $bucketKst = $bucketUtc.AddHours(9)

                $bid = [double]::Parse($r.BID, [System.Globalization.CultureInfo]::InvariantCulture)
                $ask = [double]::Parse($r.ASK, [System.Globalization.CultureInfo]::InvariantCulture)
                $spread = [double]::Parse($r.SPREAD, [System.Globalization.CultureInfo]::InvariantCulture)
                $last = [double]::Parse($r.LAST, [System.Globalization.CultureInfo]::InvariantCulture)
                $volume = [double]::Parse($r.VOLUME, [System.Globalization.CultureInfo]::InvariantCulture)
            } catch {
                Write-ErrorLog "SKIP parse error in $($file.Name): $($_.Exception.Message)"
                continue
            }

            $key = "{0}|{1}|{2}|{3}" -f $bucketUtc.Ticks, $r.BROKER, $r.SERVER, $r.SYMBOL

            if (-not $groups.ContainsKey($key)) {
                $groups[$key] = [ordered]@{
                    TIME_UTC = $bucketUtc.ToString("yyyy-MM-dd HH:mm:ss")
                    TIME_KST = $bucketKst.ToString("yyyy-MM-dd HH:mm:ss")
                    BROKER = $r.BROKER
                    SERVER = $r.SERVER
                    SYMBOL = $r.SYMBOL
                    FIRST_MSC = $msc
                    LAST_MSC = $msc
                    FIRST_SEQ = $rawSequence
                    LAST_SEQ = $rawSequence
                    BID_OPEN = $bid; BID_HIGH = $bid; BID_LOW = $bid; BID_CLOSE = $bid
                    ASK_OPEN = $ask; ASK_HIGH = $ask; ASK_LOW = $ask; ASK_CLOSE = $ask
                    SPREAD_OPEN = $spread; SPREAD_HIGH = $spread; SPREAD_LOW = $spread; SPREAD_CLOSE = $spread
                    LAST_OPEN = $last; LAST_HIGH = $last; LAST_LOW = $last; LAST_CLOSE = $last
                    TICK_COUNT = 1
                    VOLUME_LAST = $volume
                    VOLUME_MAX = $volume
                }
            } else {
                $g = $groups[$key]
                $g.TICK_COUNT++

                if ($bid -gt $g.BID_HIGH) { $g.BID_HIGH = $bid }
                if ($bid -lt $g.BID_LOW) { $g.BID_LOW = $bid }
                if ($ask -gt $g.ASK_HIGH) { $g.ASK_HIGH = $ask }
                if ($ask -lt $g.ASK_LOW) { $g.ASK_LOW = $ask }
                if ($spread -gt $g.SPREAD_HIGH) { $g.SPREAD_HIGH = $spread }
                if ($spread -lt $g.SPREAD_LOW) { $g.SPREAD_LOW = $spread }
                if ($last -gt $g.LAST_HIGH) { $g.LAST_HIGH = $last }
                if ($last -lt $g.LAST_LOW) { $g.LAST_LOW = $last }
                if ($volume -gt $g.VOLUME_MAX) { $g.VOLUME_MAX = $volume }

                if (($msc -lt $g.FIRST_MSC) -or (($msc -eq $g.FIRST_MSC) -and ($rawSequence -lt $g.FIRST_SEQ))) {
                    $g.FIRST_MSC = $msc
                    $g.FIRST_SEQ = $rawSequence
                    $g.BID_OPEN = $bid
                    $g.ASK_OPEN = $ask
                    $g.SPREAD_OPEN = $spread
                    $g.LAST_OPEN = $last
                }
                if (($msc -gt $g.LAST_MSC) -or (($msc -eq $g.LAST_MSC) -and ($rawSequence -gt $g.LAST_SEQ))) {
                    $g.LAST_MSC = $msc
                    $g.LAST_SEQ = $rawSequence
                    $g.BID_CLOSE = $bid
                    $g.ASK_CLOSE = $ask
                    $g.SPREAD_CLOSE = $spread
                    $g.LAST_CLOSE = $last
                    $g.VOLUME_LAST = $volume
                }
            }

            if (-not $brokerLatest.ContainsKey($r.BROKER) -or $msc -gt $brokerLatest[$r.BROKER].MSC) {
                $brokerLatest[$r.BROKER] = [pscustomobject]@{ MSC = $msc; SYMBOL = $r.SYMBOL; UTC = $utc }
            }
        }
    }

    $headers = @(
        "TIME_UTC","TIME_KST","BROKER","SERVER","SYMBOL",
        "BID_OPEN","BID_HIGH","BID_LOW","BID_CLOSE",
        "ASK_OPEN","ASK_HIGH","ASK_LOW","ASK_CLOSE",
        "SPREAD_OPEN","SPREAD_HIGH","SPREAD_LOW","SPREAD_CLOSE",
        "LAST_OPEN","LAST_HIGH","LAST_LOW","LAST_CLOSE",
        "TICK_COUNT","VOLUME_LAST","VOLUME_MAX"
    )

    $outputRows = foreach ($g in $groups.Values) {
        [pscustomobject]@{
            TIME_UTC = $g.TIME_UTC; TIME_KST = $g.TIME_KST; BROKER = $g.BROKER; SERVER = $g.SERVER; SYMBOL = $g.SYMBOL
            BID_OPEN = $g.BID_OPEN; BID_HIGH = $g.BID_HIGH; BID_LOW = $g.BID_LOW; BID_CLOSE = $g.BID_CLOSE
            ASK_OPEN = $g.ASK_OPEN; ASK_HIGH = $g.ASK_HIGH; ASK_LOW = $g.ASK_LOW; ASK_CLOSE = $g.ASK_CLOSE
            SPREAD_OPEN = $g.SPREAD_OPEN; SPREAD_HIGH = $g.SPREAD_HIGH; SPREAD_LOW = $g.SPREAD_LOW; SPREAD_CLOSE = $g.SPREAD_CLOSE
            LAST_OPEN = $g.LAST_OPEN; LAST_HIGH = $g.LAST_HIGH; LAST_LOW = $g.LAST_LOW; LAST_CLOSE = $g.LAST_CLOSE
            TICK_COUNT = $g.TICK_COUNT; VOLUME_LAST = $g.VOLUME_LAST; VOLUME_MAX = $g.VOLUME_MAX
        }
    }

    $outputRows = @($outputRows | Sort-Object TIME_UTC, BROKER, SERVER, SYMBOL)
    if ($outputRows.Count -eq 0) { throw "No valid 5-minute rows were generated." }

    Write-MarketDataXlsx -Path $TempXlsx -Headers $headers -Rows $outputRows
    if (-not (Test-MarketDataXlsx -Path $TempXlsx -ExpectedHeaders $headers)) { throw "TEMP XLSX validation failed: $TempXlsx" }
    Replace-LocalFileSafely -TempPath $TempXlsx -FinalPath $OutputXlsx
    Write-Log "XLSX UPDATED: $OutputXlsx / Rows=$($outputRows.Count)"

    foreach ($broker in @("EZSquare", "CultureCapital")) {
        if ($brokerLatest.ContainsKey($broker)) {
            $latest = $brokerLatest[$broker]
            $ageMin = (([DateTime]::UtcNow - $latest.UTC).TotalMinutes)

            if ($ageMin -le 5) {
                $status = "RUNNING"
            } elseif ([DateTime]::UtcNow.DayOfWeek -in @([DayOfWeek]::Saturday, [DayOfWeek]::Sunday)) {
                $status = "MARKET_CLOSED"
            } else {
                $status = "STALE"
            }

            Write-Health $broker $status ("LatestUTC={0};LastSymbol={1};AgeMinutes={2:N1}" -f $latest.UTC.ToString("yyyy-MM-dd HH:mm:ss"), $latest.SYMBOL, $ageMin)
        } else {
            $status = if ([DateTime]::UtcNow.DayOfWeek -in @([DayOfWeek]::Saturday, [DayOfWeek]::Sunday)) { "MARKET_CLOSED" } else { "NO_TICK" }
            Write-Health $broker $status "No raw rows in current lookback input."
        }
    }

    

    Write-Log "SUCCESS Market Data processing completed."
    exit 0
}
catch {
    $fatalMessage = "FATAL: " + $_.Exception.Message
    try { Write-ErrorLog $fatalMessage } catch { Write-Host $fatalMessage -ForegroundColor Red }

    if (Test-Path -LiteralPath $AutoSyncDir -PathType Container) {
        foreach ($broker in @("EZSquare", "CultureCapital")) {
            try { Write-Health $broker "FILE_ERROR" $fatalMessage } catch {}
        }
    }

    if (Test-Path -LiteralPath $TempXlsx) { Remove-Item -LiteralPath $TempXlsx -Force -ErrorAction SilentlyContinue }
    exit 1
}
