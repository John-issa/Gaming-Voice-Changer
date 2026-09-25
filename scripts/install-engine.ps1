<#
.SYNOPSIS
    Download, verify and unpack the pinned RVC realtime GUI package into engine\.
.DESCRIPTION
    Reads config\engine.lock.json. The ~7.8 GB archive is downloaded to downloads\ with a
    resumable curl.exe, checked against the pinned size and SHA256 (a mismatch stops the
    script), extracted to a temporary folder, and the folder that contains
    go-realtime_gui.bat is moved to engine\. Then the files the hotkey add-on depends on
    are checked.

    Safe to run again: an existing, complete engine\ is only re-checked, and an
    interrupted download resumes. Needs no admin rights.
.PARAMETER SkipDownload
    Don't download. Use the archive that is already in downloads\ (for example one you
    downloaded in a browser). It is still size- and SHA256-checked.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install-engine.ps1
#>
[CmdletBinding()]
param([switch]$SkipDownload)

. (Join-Path $PSScriptRoot 'common.ps1')
trap { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }

$lock = Read-Json (Join-Path $Repo 'config\engine.lock.json')
$downloads = Join-Path $Repo 'downloads'
$archive = Join-Path $downloads $lock.file
$engine = Join-Path $Repo $lock.install_dir
$size = [long]$lock.size

function Get-MissingFiles([string]$Dir) {
    @($lock.required_files | Where-Object { -not (Test-Path -LiteralPath (Join-Path $Dir $_)) })
}

# What vcgui\hotkey_launcher.py relies on in realtime_gui.py, plus the bundled models that
# would otherwise be fetched at runtime. Missing items are warnings: the stock GUI may still work.
function Test-EngineAnchors([string]$Dir) {
    $gui = Join-Path $Dir 'realtime_gui.py'
    $anchors = @(
        'if __name__ == "__main__":',
        'import FreeSimpleGUI as sg',
        'sg.Window("RVC - GUI"',
        'key="im"',
        'key="vc"',
        'elif event in ["vc", "im"]'
    )
    $problems = @()
    foreach ($a in $anchors) {
        if (-not (Select-String -LiteralPath $gui -SimpleMatch -Pattern $a -Quiet)) {
            $problems += "realtime_gui.py no longer contains: $a"
        }
    }
    # 2.3.260718 loads HuBERT in transformers format with local_files_only=True (infer\hubert.py).
    foreach ($f in @('assets\hubert_base\config.json', 'assets\hubert_base\pytorch_model.bin',
                     'assets\rmvpe\rmvpe.pt')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Dir $f))) { $problems += "missing bundled model: $f" }
    }
    if ($problems.Count -eq 0) {
        Write-Host 'Engine check passed: realtime_gui.py has every anchor the hotkey add-on needs, and hubert + rmvpe are bundled.'
        return
    }
    Write-Warning ('=' * 70)
    Write-Warning 'This engine differs from what the hotkey add-on was written against:'
    foreach ($p in $problems) { Write-Warning "  - $p" }
    Write-Warning 'The stock go-realtime_gui.bat may still work, but launch.bat / the hotkey may not.'
    Write-Warning ('=' * 70)
}

# 1. Already installed?
if (Test-Path -LiteralPath $engine) {
    $missing = @(Get-MissingFiles $engine)
    if ($missing.Count -gt 0) {
        throw ("$engine exists but is incomplete (missing: {0}). Rename or delete that folder, then run this script again." -f ($missing -join ', '))
    }
    Write-Host "Engine already installed in $engine"
    Test-EngineAnchors $engine
    exit 0
}

# The 2.3.260718 package unpacks to 15.43 GB (1.98 x the archive); keep 1 GB spare on top.
$unpacked = [long]($size * 2) + 1GB
function Assert-FreeSpace([long]$Needed, [string]$What) {
    $drive = Get-PSDrive -Name $Repo.Substring(0, 1) -ErrorAction SilentlyContinue
    if ($drive -and $drive.Free -lt $Needed) {
        throw ("{0} needs about {1} free on {2}: but only {3} is free. Free up space and run this script again." -f
               $What, (Format-Size $Needed), $drive.Name, (Format-Size $drive.Free))
    }
}

# 2. Download (resumable) and verify.
$have = Get-PartialSize $archive
if ($SkipDownload) {
    if ($have -eq 0) {
        throw "-SkipDownload was given but $archive does not exist. Put the archive there or drop -SkipDownload."
    }
    if ($have -lt $size) {
        throw ("{0} is incomplete ({1} of {2}). Run this script without -SkipDownload to resume the download." -f
               $archive, (Format-Size $have), (Format-Size $size))
    }
}
if ((Test-Path -LiteralPath $archive) -and (Get-Item -LiteralPath $archive).Length -eq $size) {
    Write-Host ("Checking size and SHA256 of {0} ({1}); this takes a minute or two..." -f $lock.file, (Format-Size $size))
    $problem = Test-PinnedFile $archive $size $lock.sha256
    if ($problem) { throw "Refusing to install: $archive $problem. Delete the file and run this script again." }
} else {
    Assert-FreeSpace ($size - $have + $unpacked) 'Downloading and unpacking the engine'
    Get-PinnedFile $lock.url $archive $size $lock.sha256
}
Write-Host "SHA256 OK: $($lock.sha256)"

# 3. Extract to a temp folder next to engine\ (same drive, so the final move is a rename).
Assert-FreeSpace $unpacked 'Unpacking the engine'
$tmp = Join-Path $downloads '_extract'
if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force }
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $sevenZip = Find-SevenZip
    if ($sevenZip) {
        Write-Host "Extracting with $sevenZip ..."
        Invoke-Native $sevenZip @('x', $archive, "-o$tmp", '-y', '-bso0', '-bsp2')
        if ($LASTEXITCODE -ne 0) { throw "7-Zip failed (exit $LASTEXITCODE)." }
    } else {
        Write-Host 'Extracting with Windows tar.exe (slower, no progress bar; installing 7-Zip makes this faster) ...'
        $skipped = @(Invoke-TarExtract $archive $tmp)
        if ($skipped.Count -gt 0) {
            Write-Warning ("tar.exe skipped {0} file(s) whose names use non-ASCII characters (the package's Chinese license text and demo audio in TEMP\); the engine doesn't need them." -f $skipped.Count)
        }
    }
    $bat = Get-ChildItem -LiteralPath $tmp -Recurse -Depth 3 -Filter 'go-realtime_gui.bat' -File |
        Select-Object -First 1
    if (-not $bat) { throw 'No go-realtime_gui.bat found in the archive.' }
    Move-Item -LiteralPath $bat.DirectoryName -Destination $engine
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue  # up to 15 GB
}

# 4. Verify.
$missing = @(Get-MissingFiles $engine)
if ($missing.Count -gt 0) { throw ("Installed, but these required files are missing: {0}" -f ($missing -join ', ')) }
Write-Host "Engine installed in $engine"
Test-EngineAnchors $engine
Write-Host "The archive is still in $downloads; delete it to free $(Format-Size $size) once everything works."
