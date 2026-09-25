<#
.SYNOPSIS
    Measure the voice changer's end-to-end delay: raw headset mic vs CABLE Output.
.DESCRIPTION
    Records the raw mic and CABLE Output (what the game hears) at the same time with FFmpeg
    (DirectShow) and finds where your "ta!" starts in each track. The difference is the delay.

    One clock for both tracks: each DirectShow input is stamped with the system wall clock
    (-use_wallclock_as_timestamps 1, Unix time) and the capture keeps those stamps
    (-copyts into .mkv), because FFmpeg otherwise shifts each input to start at zero on its
    own and the devices open seconds apart. The analysis reads both tracks from that one file
    (-copyts -start_at_zero subtracts the same file start time from both), and GO is recorded
    on the same wall clock, so sounds before GO (a breath, a click) are ignored.

    Start the voice changer first (launch.bat, click "Start audio conversion", converted
    voice on). Stay quiet, then say one short, sharp "ta!" when GO appears. The capture and a
    report are saved in captures\. Needs FFmpeg on PATH. Exits 1 if no delay was measured.
.PARAMETER Mic
    Substrings that must all appear in the mic's DirectShow name. Default: Audeze Maxwell, Chat.
.PARAMETER Cable
    Substrings for the virtual cable's recording side. Default: CABLE Output.
.PARAMETER Seconds
    Recording length. Default 12.
.PARAMETER PromptAt
    Seconds of silence recorded after both devices are open, before GO is shown. Default 3.
.PARAMETER NoiseDb
    Level (dBFS) below which audio counts as silence. Default: 20 dB below each track's
    loudest peak (clamped to -60..-20). Set it (e.g. -25 or -40) if the onset looks wrong.
.PARAMETER BufferMs
    DirectShow audio buffer in ms (FFmpeg's default is ~500 ms, far too coarse). Default 15.
.PARAMETER ListDevices
    Print the DirectShow audio capture devices and exit.
.PARAMETER Analyze
    Don't record; re-analyze an existing capture (for example with another -NoiseDb).
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\measure-delay.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\measure-delay.ps1 -Analyze captures\delay-20260924-201500.mkv -NoiseDb -35
#>
[CmdletBinding()]
param(
    [string[]]$Mic = @('Audeze Maxwell', 'Chat'),
    [string[]]$Cable = @('CABLE Output'),
    [int]$Seconds = 12,
    [int]$PromptAt = 3,
    [int]$NoiseDb = -30,
    [int]$BufferMs = 15,
    [switch]$ListDevices,
    [string]$Analyze
)

. (Join-Path $PSScriptRoot 'common.ps1')
trap { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }

$fixedNoiseDb = $PSBoundParameters.ContainsKey('NoiseDb')
$ffmpegCmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
if (-not $ffmpegCmd) { throw 'FFmpeg is not on PATH. Install it (winget install Gyan.FFmpeg), then open a new terminal.' }
$ffmpeg = $ffmpegCmd.Source
$inv = [Globalization.CultureInfo]::InvariantCulture

# Runs ffmpeg with its log captured (ffmpeg logs to stderr). Returns the process; log in $proc.LogFile.
function Start-FFmpeg([string[]]$Arguments) {
    $log = [IO.Path]::GetTempFileName()
    $out = [IO.Path]::GetTempFileName()
    $line = ($Arguments | ForEach-Object { ConvertTo-ArgString $_ }) -join ' '
    $proc = Start-Process -FilePath $ffmpeg -ArgumentList $line -NoNewWindow -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput $out
    $null = $proc.Handle
    $proc | Add-Member -NotePropertyName LogFile -NotePropertyValue $log
    $proc | Add-Member -NotePropertyName OutFile -NotePropertyValue $out
    return $proc
}

function Read-FFmpegLog($Proc) {
    $text = [string](Get-Content -Raw -Encoding UTF8 -LiteralPath $Proc.LogFile)  # ffmpeg writes UTF-8
    Remove-Item -LiteralPath $Proc.LogFile, $Proc.OutFile -ErrorAction SilentlyContinue
    return $text
}

function Invoke-FFmpeg([string[]]$Arguments) {
    $proc = Start-FFmpeg $Arguments
    $proc.WaitForExit()
    return @{ ExitCode = $proc.ExitCode; Log = (Read-FFmpegLog $proc) }
}

# DirectShow audio capture devices: friendly Name plus the ASCII "Alternative name" FFmpeg prints
# under it, which is what gets passed to -i (unique, and safe for any friendly name).
function Get-DshowAudioDevices {
    $r = Invoke-FFmpeg @('-hide_banner', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy')
    $devices = @()
    $last = $null
    foreach ($line in ($r.Log -split "`r?`n")) {
        $m = [regex]::Match($line, '^\[[^\]]*\]\s+"(?<name>[^"]+)"\s+\((?<kind>[^)]*)\)')
        if ($m.Success) {
            $last = $null
            if ($m.Groups['kind'].Value -match 'audio') {
                $last = [pscustomobject]@{ Name = $m.Groups['name'].Value; Alt = $null }
                $devices += $last
            }
            continue
        }
        $a = [regex]::Match($line, 'Alternative name "(?<alt>[^"]+)"')
        if ($a.Success -and $last) { $last.Alt = $a.Groups['alt'].Value; $last = $null }
    }
    return , $devices
}

function Resolve-Device($Devices, [string[]]$Substrings, [string]$What) {
    $subs = @($Substrings | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    $hits = @($Devices | Where-Object {
        $n = $_.Name
        @($subs | Where-Object { $n.IndexOf($_, [StringComparison]::OrdinalIgnoreCase) -lt 0 }).Count -eq 0
    })
    if ($hits.Count -eq 1) { return $hits[0] }
    $list = ($Devices | ForEach-Object { "    $($_.Name)" }) -join "`n"
    if ($hits.Count -eq 0) {
        throw ("No DirectShow audio device matches {0} ({1}). Is it connected/installed?`n  Audio capture devices:`n{2}" -f
               $What, ($subs -join ' + '), $list)
    }
    throw ("{0} devices match {1} ({2}): {3}. Pass a more specific -{1}." -f
           $hits.Count, $What, ($subs -join ' + '), (($hits | ForEach-Object { $_.Name }) -join '; '))
}

function ConvertTo-Double([string]$Text) { [double]::Parse($Text, [Globalization.NumberStyles]::Float, $inv) }

# Peak level and sound onset of one track. Times are seconds from the capture's start on the shared
# clock; $GoUnix (Unix seconds, same clock as the stamps) excludes anything earlier than GO - 0.5 s.
function Get-TrackInfo([string]$File, [int]$Stream, $GoUnix) {
    $info = @{ Peak = [double]::NegativeInfinity; Threshold = $null; Onset = $null; GoAt = $null }
    $v = Invoke-FFmpeg @('-hide_banner', '-nostats', '-i', $File, '-map', "0:a:$Stream", '-af', 'volumedetect', '-f', 'null', '-')
    if ($v.ExitCode -ne 0) { throw "ffmpeg could not read stream $Stream of ${File}:`n$($v.Log)" }
    $m = [regex]::Match($v.Log, 'max_volume: (-?[\d.]+) dB')
    if ($m.Success) { $info.Peak = ConvertTo-Double $m.Groups[1].Value }
    if ($info.Peak -lt -60) { return $info }  # effectively silent

    $info.Threshold = if ($fixedNoiseDb) { $NoiseDb } else { [math]::Max(-60, [math]::Min(-20, [math]::Round($info.Peak - 20))) }
    $r = Invoke-FFmpeg @('-hide_banner', '-nostats', '-copyts', '-start_at_zero', '-i', $File, '-map', "0:a:$Stream",
                         '-af', "silencedetect=noise=$($info.Threshold)dB:d=0.3", '-f', 'null', '-')
    if ($r.ExitCode -ne 0) { throw "ffmpeg could not analyze stream $Stream of ${File}:`n$($r.Log)" }
    $s = [regex]::Match($r.Log, 'start: (\d+\.\d+)')  # the file's start on the wall clock
    if ($GoUnix -and $s.Success) { $info.GoAt = [double]$GoUnix - (ConvertTo-Double $s.Groups[1].Value) }
    $events = @([regex]::Matches($r.Log, 'silence_(start|end): (-?[\d.]+(?:e[-+]?\d+)?)') | ForEach-Object {
        [pscustomobject]@{ Kind = $_.Groups[1].Value; T = (ConvertTo-Double $_.Groups[2].Value) } })
    # Onset = the end of a silence (at or after GO - 0.5 s) that is followed by silence again later;
    # a lone final silence_end can just mark the end of the file.
    for ($i = 1; $i -lt $events.Count; $i++) {
        $e = $events[$i]
        if ($e.Kind -ne 'end' -or $events[$i - 1].Kind -ne 'start') { continue }
        if ($null -ne $info.GoAt -and $e.T -lt $info.GoAt - 0.5) { continue }
        $silenceAgain = $false
        for ($j = $i + 1; $j -lt $events.Count; $j++) { if ($events[$j].Kind -eq 'start') { $silenceAgain = $true; break } }
        if ($silenceAgain) { $info.Onset = $e.T }
        break
    }
    return $info
}

# Returns @{ Ok; Lines } and prints the lines.
function Measure-Capture([string]$File) {
    $goUnix = $null
    $sidecar = [IO.Path]::ChangeExtension($File, '.json')
    if (Test-Path -LiteralPath $sidecar) { $goUnix = Get-Prop (Read-Json $sidecar) 'go_unix' $null }
    $tracks = [ordered]@{ mic = (Get-TrackInfo $File 0 $goUnix); cable = (Get-TrackInfo $File 1 $goUnix) }
    $lines = @("Capture : $File")
    if (-not $goUnix) { $lines += 'GO time : unknown (no .json next to the capture); the first sound in each track counts' }
    $ok = $true
    foreach ($name in $tracks.Keys) {
        $t = $tracks[$name]
        $label = @{ mic = 'Mic  '; cable = 'Cable' }[$name]
        if ($t.Peak -lt -60) {
            $lines += @{
                mic   = "Mic   : silent (peak $($t.Peak) dBFS). Is the mic muted, or is -Mic the wrong device?"
                cable = "Cable : silent (peak $($t.Peak) dBFS). Is the voice changer running, with 'Output converted voice' selected and CABLE Input as its output device?"
            }[$name]
            $ok = $false
        } elseif ($null -eq $t.Onset) {
            $lines += "${label} : no clear 'silence, then sound, then silence' after GO (peak $($t.Peak) dBFS, threshold $($t.Threshold) dB). Stay quiet until GO and record again, or try -NoiseDb."
            $ok = $false
        } else {
            $when = if ($null -ne $t.GoAt) { '{0:N3} s after GO' -f ($t.Onset - $t.GoAt) } else { '{0:N3} s into the capture' -f $t.Onset }
            $lines += ('{0} : sound starts {1} (peak {2} dBFS, threshold {3} dB)' -f $label, $when, $t.Peak, $t.Threshold)
        }
    }
    if ($ok) {
        $delayMs = [math]::Round(($tracks.cable.Onset - $tracks.mic.Onset) * 1000)
        $lines += "End-to-end delay (cable - mic): $delayMs ms"
        if ($delayMs -lt 0 -or $delayMs -gt 1500) {
            $lines += 'This value is implausible: one track probably caught a different sound. Record again, or try -NoiseDb.'
            $ok = $false
        } elseif ($delayMs -le 300) {
            $lines += 'Within the <= ~300 ms target.'
        } else {
            $lines += 'Above the ~300 ms target. See docs\tuning.md (lower block_time, then extra_time).'
        }
    }
    $lines | ForEach-Object { Write-Host $_ }
    return @{ Ok = $ok; Lines = $lines }
}

if ($Analyze) {
    $result = Measure-Capture (Resolve-Path -LiteralPath $Analyze).Path
    if ($result.Ok) { exit 0 } else { exit 1 }
}

$devices = Get-DshowAudioDevices
if ($ListDevices) {
    Write-Host 'DirectShow audio capture devices:'
    $devices | ForEach-Object { Write-Host "  $($_.Name)" }
    exit 0
}
$micDev = Resolve-Device $devices $Mic 'Mic'
$cableDev = Resolve-Device $devices $Cable 'Cable'

$captures = Join-Path $Repo 'captures'
New-Item -ItemType Directory -Force -Path $captures | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$mkv = Join-Path $captures "delay-$stamp.mkv"

function Get-DshowInput($Dev) {
    $id = if ($Dev.Alt) { $Dev.Alt } else { $Dev.Name }
    # -t per input: each device records $Seconds s from the moment it opened.
    return @('-f', 'dshow', '-audio_buffer_size', "$BufferMs", '-use_wallclock_as_timestamps', '1',
             '-t', "$Seconds", '-i', "audio=$id")
}
$ffArgs = @('-hide_banner', '-nostats', '-nostdin', '-y') + (Get-DshowInput $micDev) + (Get-DshowInput $cableDev) +
          @('-map', '0:a', '-map', '1:a', '-c:a', 'pcm_s16le', '-copyts', $mkv)

Write-Host "Mic   : $($micDev.Name)"
Write-Host "Cable : $($cableDev.Name)"
Write-Host "Opening both devices. Stay quiet until GO, then say one short, sharp 'ta!' and stay quiet again."
$proc = Start-FFmpeg $ffArgs
# FFmpeg opens the devices one after the other (seconds apart), and whatever the first one
# captures in the meantime gets bunched-up timestamps. Count down only once both are live.
$sw = [Diagnostics.Stopwatch]::StartNew()
while (-not $proc.HasExited -and -not (Select-String -LiteralPath $proc.LogFile -SimpleMatch 'Output #0' -Quiet)) {
    if ($sw.Elapsed.TotalSeconds -gt 30) {
        Stop-Process -Id $proc.Id -Force
        throw "The devices did not open within 30 s. FFmpeg log: $($proc.LogFile)"
    }
    Start-Sleep -Milliseconds 100
}
$openSeconds = $sw.Elapsed.TotalSeconds
if ($openSeconds -gt $Seconds - $PromptAt - 3) {
    Write-Warning ("Opening the devices took {0:N1} s, so the first one may stop recording early. If no onset is found, use -Seconds {1}." -f $openSeconds, [math]::Ceiling($openSeconds + $PromptAt + 6))
}
for ($i = $PromptAt; $i -gt 0 -and -not $proc.HasExited; $i--) {
    Write-Host "  $i..."
    Start-Sleep -Seconds 1
}
$goUnix = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0  # same clock as the capture's stamps
if (-not $proc.HasExited) { Write-Host '  >>> GO: say "ta!" now <<<' -ForegroundColor Yellow }
if (-not $proc.WaitForExit(($Seconds + 20) * 1000)) {
    Stop-Process -Id $proc.Id -Force
    throw "ffmpeg did not stop after $Seconds s; log: $($proc.LogFile)"
}
$log = Read-FFmpegLog $proc
if ($proc.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $mkv)) {
    throw "Recording failed (ffmpeg exit $($proc.ExitCode)):`n$log"
}
@{ go_unix = $goUnix; mic = $micDev.Name; cable = $cableDev.Name; buffer_ms = $BufferMs } | ConvertTo-Json |
    Set-Content -Encoding UTF8 -LiteralPath ([IO.Path]::ChangeExtension($mkv, '.json'))

Write-Host ''
$result = Measure-Capture $mkv
$result.Lines | Set-Content -Encoding UTF8 -LiteralPath ([IO.Path]::ChangeExtension($mkv, '.txt'))
if ($result.Ok) { exit 0 } else { exit 1 }
