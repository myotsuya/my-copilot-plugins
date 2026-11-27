param(
    [Parameter(Mandatory=$true)][string]$XmlPath,
    [Parameter(Mandatory=$true)][string]$OutputZip
)
$ErrorActionPreference = 'Stop'
$inputFile = (Resolve-Path -LiteralPath $XmlPath).Path
$outputFile = [IO.Path]::GetFullPath($OutputZip)
if (Test-Path -LiteralPath $outputFile) { throw 'Output already exists. Choose a new output path.' }
$xmlBytes = [IO.File]::ReadAllBytes($inputFile)
$utf8 = New-Object System.Text.UTF8Encoding($false, $true)
$xmlText = $utf8.GetString($xmlBytes)
if (-not $xmlText.StartsWith('<?xml')) { throw 'UTF-8 XML declaration required; BOM is not supported.' }
$settings = New-Object System.Xml.XmlReaderSettings
$settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
$settings.XmlResolver = $null
$reader = [System.Xml.XmlReader]::Create((New-Object System.IO.StringReader($xmlText)), $settings)
try {
    $doc = New-Object System.Xml.XmlDocument
    $doc.XmlResolver = $null
    $doc.Load($reader)
    if ($doc.DocumentElement.Name -ne 'DatabaseXmlWrapper') { throw 'Unexpected XML root.' }
} finally { $reader.Dispose() }
$md5 = [Security.Cryptography.MD5]::Create()
try { $certificate = ([BitConverter]::ToString($md5.ComputeHash($xmlBytes))).Replace('-', '').ToLowerInvariant() }
finally { $md5.Dispose() }
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$stream = [IO.File]::Open($outputFile, [IO.FileMode]::CreateNew)
try {
    $zip = New-Object System.IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create, $true)
    try {
        foreach ($name in @('databasedef.xml', 'certificate.txt')) {
            $entry = $zip.CreateEntry($name, [IO.Compression.CompressionLevel]::Optimal)
            $entryStream = $entry.Open()
            try {
                $bytesToWrite = if ($name -eq 'databasedef.xml') { $xmlBytes } else { [Text.Encoding]::ASCII.GetBytes($certificate) }
                $entryStream.Write($bytesToWrite, 0, $bytesToWrite.Length)
            } finally { $entryStream.Dispose() }
        }
    } finally { $zip.Dispose() }
} finally { $stream.Dispose() }
$check = [IO.Compression.ZipFile]::OpenRead($outputFile)
try {
    if ($check.Entries.Count -ne 2) { throw 'Unexpected ZIP entry count.' }
    foreach ($name in @('databasedef.xml', 'certificate.txt')) {
        $entryStream = $check.GetEntry($name).Open()
        $memory = New-Object System.IO.MemoryStream
        try {
            $entryStream.CopyTo($memory)
            $expected = if ($name -eq 'databasedef.xml') { $xmlBytes } else { [Text.Encoding]::ASCII.GetBytes($certificate) }
            if ([Convert]::ToBase64String($memory.ToArray()) -ne [Convert]::ToBase64String($expected)) { throw 'ZIP byte verification failed.' }
        } finally { $memory.Dispose(); $entryStream.Dispose() }
    }
} finally { $check.Dispose() }
Write-Output ('ZIP created; byte integrity checked. SHA256=' + (Get-FileHash -LiteralPath $outputFile -Algorithm SHA256).Hash.ToLowerInvariant())
Write-Output 'POWER EGG import NOT tested. This packaging script does not validate ID references or layouts.'
