# Shared helpers for the scripts in this folder. Dot-source it: . (Join-Path $PSScriptRoot 'common.ps1')
# Windows PowerShell 5.1 compatible. Never needs admin.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent $PSScriptRoot

function Read-Json([string]$Path) {
    Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json
}

# Property value, or $Default when the JSON object doesn't have it (StrictMode-safe).
function Get-Prop($Object, [string]$Name, $Default = $null) {
    $p = $Object.PSObject.Properties[$Name]
    if ($p) { return $p.Value }
    return $Default
}

# Runs a native exe; check $LASTEXITCODE afterwards. Its stderr (progress bars, warnings) never
# becomes a terminating error, even in hosts that redirect it (ISE, CI, captured output).
function Invoke-Native([string]$Exe, [string[]]$Arguments) {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { & $Exe @Arguments } finally { $ErrorActionPreference = $saved }
}

# Quotes one argument for a Windows command line (MSVC/CommandLineToArgvW rules).
function ConvertTo-ArgString([string]$Arg) {
    if ($Arg -and $Arg -notmatch '[\s"]') { return $Arg }
    $escaped = $Arg -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

# Runs an exe attached to this console, the way cmd.exe would, and returns its exit code.
# Unlike "& exe", its stdout stays a real console, so Python output is unbuffered and
# its console encoding (UTF-8 via chcp 65001) is used.
function Invoke-Console([string]$Exe, [string[]]$Arguments) {
    $line = ($Arguments | ForEach-Object { ConvertTo-ArgString $_ }) -join ' '
    $proc = Start-Process -FilePath $Exe -ArgumentList $line -NoNewWindow -PassThru
    $null = $proc.Handle  # Windows PowerShell 5.1 loses ExitCode unless the handle is opened early
    $proc.WaitForExit()
    return $proc.ExitCode
}

function Get-CurlExe {
    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    if (Test-Path -LiteralPath $curl) { return $curl }
    return 'curl.exe'
}

function Format-Size([long]$Bytes) {
    if ($Bytes -ge 1GB) { return '{0:N2} GB' -f ($Bytes / 1GB) }
    return '{0:N1} MB' -f ($Bytes / 1MB)
}

# Size + SHA256 check. Returns $null when the file matches, otherwise the reason.
function Test-PinnedFile([string]$Path, [long]$Size, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Path)) { return 'missing' }
    $have = (Get-Item -LiteralPath $Path).Length
    if ($have -ne $Size) { return "size is $have bytes, expected $Size" }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    if ($hash -ne $Sha256.ToLowerInvariant()) { return "SHA256 is $hash, expected $Sha256" }
    return $null
}

# Bytes of $Dest already downloaded (in "$Dest.part", or a partial $Dest left by an older version).
function Get-PartialSize([string]$Dest) {
    foreach ($p in @("$Dest.part", $Dest)) {
        if (Test-Path -LiteralPath $p) { return (Get-Item -LiteralPath $p).Length }
    }
    return 0L
}

# Resumable, verified download of a pinned file. curl writes "$Dest.part"; it becomes $Dest only
# once size and SHA256 match, so a file at $Dest is never a partial download.
function Get-PinnedFile([string]$Url, [string]$Dest, [long]$Size, [string]$Sha256) {
    $part = "$Dest.part"
    $name = Split-Path -Leaf $Dest
    if (Test-Path -LiteralPath $Dest) {
        $len = (Get-Item -LiteralPath $Dest).Length
        if ($len -gt $Size) { throw "$Dest is larger than expected ($len > $Size bytes). Delete it and run this script again." }
        if (-not (Test-Path -LiteralPath $part)) { Move-Item -LiteralPath $Dest -Destination $part }  # resume it
        else { Remove-Item -LiteralPath $Dest }
    }
    $have = 0L
    if (Test-Path -LiteralPath $part) { $have = (Get-Item -LiteralPath $part).Length }
    if ($have -gt $Size) { Remove-Item -LiteralPath $part; $have = 0L }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dest) | Out-Null
    if ($have -gt 0) {
        Write-Host ("Resuming {0} at {1} of {2}" -f $name, (Format-Size $have), (Format-Size $Size))
    } else {
        Write-Host ("Downloading {0} ({1})" -f $name, (Format-Size $Size))
    }
    if ($have -lt $Size) {
        Invoke-Native (Get-CurlExe) @('-L', '-C', '-', '--fail', '--retry', '5', '--retry-delay', '10',
                                      '-o', $part, $Url)
        if ($LASTEXITCODE -ne 0) {
            throw "curl.exe failed (exit $LASTEXITCODE). Run this script again to resume the download."
        }
    }
    $have = (Get-Item -LiteralPath $part).Length
    if ($have -ne $Size) { throw "$part is $have bytes, expected $Size. Run this script again to resume." }
    if ($Size -ge 1GB) { Write-Host "Checking SHA256 of $name; this takes a minute or two..." }
    $problem = Test-PinnedFile $part $Size $Sha256
    if ($problem) {
        Remove-Item -LiteralPath $part
        throw "The download of $name was corrupt ($problem) and has been deleted. Run this script again."
    }
    Move-Item -LiteralPath $part -Destination $Dest
}

# 7z.exe from 7-Zip (or 7za.exe): Program Files (64- and 32-bit), then PATH.
function Find-SevenZip {
    $dirs = @($env:ProgramW6432, $env:ProgramFiles, ${env:ProgramFiles(x86)}) | Where-Object { $_ }
    foreach ($d in $dirs) {
        $exe = Join-Path $d '7-Zip\7z.exe'
        if (Test-Path -LiteralPath $exe) { return $exe }
    }
    $cmd = Get-Command 7z.exe, 7za.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return $null
}

# Extracts a .7z with Windows' own tar.exe (bsdtar). bsdtar can't represent names outside the
# ANSI code page and skips those entries with exit code 1; that is tolerated (callers verify the
# files they need) and the skipped names are returned. Any other error throws.
function Invoke-TarExtract([string]$Archive, [string]$Destination) {
    $tar = Join-Path $env:SystemRoot 'System32\tar.exe'
    $log = [IO.Path]::GetTempFileName()
    $out = [IO.Path]::GetTempFileName()
    try {
        $line = (@('-xf', $Archive, '-C', $Destination) | ForEach-Object { ConvertTo-ArgString $_ }) -join ' '
        $proc = Start-Process -FilePath $tar -ArgumentList $line -NoNewWindow -PassThru `
            -RedirectStandardError $log -RedirectStandardOutput $out
        $null = $proc.Handle
        $proc.WaitForExit()
        $errors = @(Get-Content -Encoding UTF8 -LiteralPath $log | Where-Object { $_.Trim() })
    } finally {
        Remove-Item -LiteralPath $log, $out -ErrorAction SilentlyContinue
    }
    if ($proc.ExitCode -eq 0) { return , @() }
    $skipped = @($errors | Where-Object { $_ -match 'unreadable filename' })
    $other = @($errors | Where-Object { $_ -notmatch 'unreadable filename|Error exit delayed' })
    if ($proc.ExitCode -eq 1 -and $skipped.Count -gt 0 -and $other.Count -eq 0) { return , $skipped }
    throw ("tar.exe failed (exit {0}):`n{1}" -f $proc.ExitCode, ($errors -join "`n"))
}
