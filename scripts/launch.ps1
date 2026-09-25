<#
.SYNOPSIS
    Start the RVC realtime GUI with a voice preset and the vc/im toggle hotkey.
.DESCRIPTION
    Runs vcgui\hotkey_launcher.py on the engine's own Python. The launcher merges the
    preset into engine\configs\config.json, resolves the audio devices from
    config\audio.json and opens the stock RVC window. Press Start there to begin.
    The hotkey from config\hotkey.json (default Ctrl+Alt+V) switches between the
    converted voice (vc) and your raw mic (im).
.PARAMETER Preset
    A file name from config\presets without .json. Default: vctk-p231.
.PARAMETER NoCudaGraph
    Set RVC_CUDA_GRAPH=0 to turn off the engine's CUDA Graph path (try it if conversion misbehaves).
.PARAMETER ListDevices
    Print the audio devices per host API, as the engine sees them, and exit.
.PARAMETER ListPresets
    Print the available presets and exit.
.EXAMPLE
    launch.bat -Preset vctk-p238
#>
[CmdletBinding()]
param(
    [string]$Preset = 'vctk-p231',
    [switch]$NoCudaGraph,
    [switch]$ListDevices,
    [switch]$ListPresets
)

. (Join-Path $PSScriptRoot 'common.ps1')
trap { Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }

$engine = Join-Path $Repo 'engine'
$python = Join-Path $engine 'runtime\python.exe'
$launcher = Join-Path $Repo 'vcgui\hotkey_launcher.py'

if ($ListPresets) {
    foreach ($f in Get-ChildItem -LiteralPath (Join-Path $Repo 'config\presets') -Filter '*.json' -File) {
        Write-Host ("{0,-16} {1}" -f $f.BaseName, (Get-Prop (Read-Json $f.FullName) 'label' ''))
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $python)) {
    throw (("The RVC engine is not installed ({0} is missing).`n" +
            "  Install it with: powershell -ExecutionPolicy Bypass -File scripts\install-engine.ps1") -f $python)
}

if ($ListDevices) {
    exit (Invoke-Console $python @('-I', $launcher, '--engine', $engine, '--list-devices'))
}

$presetFile = Join-Path $Repo "config\presets\$Preset.json"
if (-not (Test-Path -LiteralPath $presetFile)) {
    $names = Get-ChildItem -LiteralPath (Join-Path $Repo 'config\presets') -Filter '*.json' -File |
        ForEach-Object { $_.BaseName }
    throw ("Unknown preset '{0}'. Available: {1}" -f $Preset, ($names -join ', '))
}
$settings = (Read-Json $presetFile).settings
foreach ($key in @('pth_path', 'index_path')) {
    $path = Get-Prop $settings $key ''
    if ($path -and -not [IO.Path]::IsPathRooted($path)) { $path = Join-Path $Repo $path }
    if ($path -and -not (Test-Path -LiteralPath $path)) {
        $voice = Get-Prop (Read-Json $presetFile) 'voice' $Preset
        throw (("The voice files for preset '{0}' are missing ({1}).`n" +
                "  Download them with: powershell -ExecutionPolicy Bypass -File scripts\get-models.ps1 -Voice {2}") -f $Preset, $path, $voice)
    }
}

# Same environment as the engine's own go-realtime_gui.bat, restored afterwards so a later run
# in the same PowerShell window doesn't inherit -NoCudaGraph.
$savedPath = $env:PATH
$savedCudaGraph = $env:RVC_CUDA_GRAPH
try {
    $env:PATH = (Join-Path $engine 'runtime') + ';' + $env:PATH
    if ($NoCudaGraph) { $env:RVC_CUDA_GRAPH = '0' }
    $code = Invoke-Console $python @('-I', $launcher, '--engine', $engine, '--preset', $Preset)
} finally {
    $env:PATH = $savedPath
    $env:RVC_CUDA_GRAPH = $savedCudaGraph  # $null removes it again
}
exit $code
