<#
.SYNOPSIS
    Download the voice models listed in config\models.json into models\ and verify them.
.DESCRIPTION
    By default fetches every voice marked "default": true, without the optional files
    (the Beatrice v2 zips, only needed for the CPU-only fallback). Each file is pinned by
    revision, size and SHA256. Downloads resume, and files that already match are skipped.
    Needs no admin rights and no account.
.PARAMETER Voice
    Only these voice ids, e.g. -Voice vctk-p231,vctk-p238. Run with -List to see the ids.
.PARAMETER IncludeBeatrice
    Also download the optional Beatrice v2 zips.
.PARAMETER List
    Print the voices in the manifest and exit.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\get-models.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\get-models.ps1 -Voice vctk-p249 -IncludeBeatrice
#>
[CmdletBinding()]
param(
    [string[]]$Voice,
    [switch]$IncludeBeatrice,
    [switch]$List
)

. (Join-Path $PSScriptRoot 'common.ps1')
trap { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }

$manifest = Read-Json (Join-Path $Repo 'config\models.json')

if ($List) {
    foreach ($v in $manifest.voices) {
        $mark = if (Get-Prop $v 'default' $false) { '(default)' } else { '' }
        Write-Host ("{0,-12} {1} {2}" -f $v.id, $v.label, $mark)
    }
    exit 0
}

# "powershell -File" passes "-Voice a,b" as one string, so split on commas as well.
$ids = @($Voice | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($ids.Count -gt 0) {
    $known = @($manifest.voices | ForEach-Object { $_.id })
    $unknown = @($ids | Where-Object { $known -notcontains $_ })
    if ($unknown.Count -gt 0) {
        throw ("Unknown voice id(s): {0}. Available: {1}" -f ($unknown -join ', '), ($known -join ', '))
    }
    $voices = @($manifest.voices | Where-Object { $ids -contains $_.id })
} else {
    $voices = @($manifest.voices | Where-Object { Get-Prop $_ 'default' $false })
}

$fetched = 0
foreach ($v in $voices) {
    Write-Host "== $($v.id): $($v.label)"
    foreach ($f in $v.files) {
        if ((Get-Prop $f 'optional' $false) -and -not $IncludeBeatrice) { continue }
        $dest = Join-Path $Repo $f.local
        $name = Split-Path -Leaf $dest
        $size = [long]$f.size
        if ((Test-Path -LiteralPath $dest) -and (Get-Item -LiteralPath $dest).Length -eq $size) {
            $problem = Test-PinnedFile $dest $size $f.sha256
            if (-not $problem) { Write-Host "   ok      $name (already verified)"; continue }
            throw "$dest is complete but its $problem. Delete it and run this script again."
        }
        $url = $manifest.url_template.Replace('{revision}', $manifest.revision).Replace('{remote}', $f.remote)
        Get-PinnedFile $url $dest $size $f.sha256
        Write-Host "   ok      $name (downloaded, SHA256 verified)"
        $fetched++
    }
}

Write-Host ''
Write-Host "Done: $fetched file(s) downloaded, everything in models\ matches config\models.json."
Write-Host "Attribution (keep it when you share recordings or the voices): $($manifest.attribution)"
