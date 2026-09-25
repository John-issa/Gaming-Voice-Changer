# Performance testing

This is the acceptance protocol from the [plan](PLAN.md) (Step 0, Step 5 and Verification). You measure Overwatch without the voice changer, then with it under the same conditions, and compare the results with the targets below. Write your numbers in the [results tables](#results).

Finish the [Quick start](../README.md#quick-start) first (engine, voices, Windows audio and Overwatch settings) and connect the Maxwell.

## Targets

| Check | Pass when | Where the number comes from |
|---|---|---|
| 1% lows | "1% Low FPS" of at least 120 in each of the 3 runs with conversion on | FrameView summary |
| Stutter | No recurring stutter | Your notes, plus "0.1% Low FPS" |
| Inference time | Under about 70% of "Sample length" (block_time) during fights, e.g. under 175 ms at 0.25 s | RVC window "Inference time (ms):" or the console |
| Delay | Stable and at most about 300 ms (the plan's target) | `scripts\measure-delay.ps1` |

[tuning.md](tuning.md#reading-inference-time-ms-and-algorithmic-delaysms) explains both readouts, lists the 70% limit for other Sample length values, and explains why the starting values will probably miss the delay target.

If a target fails, change one thing at a time with the [tuning loop](tuning.md#the-tuning-loop), then repeat the three runs with conversion on. Redo the baseline only if you changed something that affects the game by itself (graphics settings, the FPS cap or Hardware-accelerated GPU scheduling). If tuning can't make every target pass, see [If acceptance still fails](#if-acceptance-still-fails).

## Tools (free, no account)

| Tool | Where | Notes |
|---|---|---|
| NVIDIA FrameView (recommended) | <https://www.nvidia.com/en-us/geforce/technologies/frameview/> | "Download Now" is a direct download of `FrameViewSetup.exe`, with no sign-in. |
| Intel PresentMon 2.x (alternative) | <https://github.com/GameTechDev/PresentMon/releases> | Open source (MIT). 2.6.0 was current in September 2026. |
| FFmpeg | `winget install Gyan.FFmpeg`, then open a new terminal | For `measure-delay.ps1` and the one-minute recording. Without it the script stops with `FFmpeg is not on PATH. ...` |

Use the same tool for all six runs: the two tools' 1% numbers are not the same statistic.

### FrameView

1. Run `FrameViewSetup.exe`. NVIDIA's user guide says to choose **Custom (Advanced)** and tick the box to perform a clean installation.
2. Open FrameView. Under **Benchmark folder location**, click **Browse** and choose where results go (the guide's example is a `FrameView` folder in Documents).
3. **Benchmark hotkey** is Scroll Lock by default. Pick F7-F12, Del or Ins instead if the game uses Scroll Lock.
4. Set **Capture duration** to a fixed number of seconds (for example 60) so every run has the same length. 0 means you stop each run with the hotkey.
5. If the overlay doesn't appear, close RivaTuner Statistics Server (RTSS) or Fraps.

Press the hotkey in the game to capture. The overlay disappears while it records and comes back with a summary. Each run adds a row to `FrameView_Summary.csv` in the benchmark folder (plus a per-frame `FrameView_<exe name>_<date and time>_Log.csv`). Copy **Avg FPS**, **1% Low FPS** and **0.1% Low FPS**. Use "1% Low FPS" (the average of the slowest 1% of frames), not the "1% FPS" column, which is a percentile.

### PresentMon (alternative)

1. Install `PresentMon-2.6.0.msi` from the releases page. Use the Capture Application it installs, not the standalone console `.exe`, which needs an elevated prompt or membership in the "Performance Log Users" group.
2. With the game in the foreground, start and stop a capture with the app's capture hotkey (Ctrl+Shift+K by default in 2.6.0; check the app's hotkey settings), or set a fixed duration.
3. Results go to `%LOCALAPPDATA%\Intel\PresentMon\Capture`: `pmcap-<exe>-<date>-<time>.csv` per frame and `pmcap-<exe>-<date>-<time>-stats.csv` as the summary. If the stats file lacks the 1% statistic, choose it in the app's statistics settings (exact label may differ by version).

PresentMon's 1% figure is a percentile, which tends to read higher than FrameView's "1% Low FPS", so the 120 FPS target is easier to pass with it. Write down which tool you used.

## 1. Prepare

1. Quit the background apps of any commercial voice changer and anything else you won't have open while gaming. Check the notification area and Task Manager.
2. Plan a Practice Range route that includes a fight with the training bots. Play the same route every time, about as long as the capture duration.
3. Choose your Overwatch graphics settings and write them down.
4. Choose the frame-rate cap as in [overwatch.md](overwatch.md#frame-rate-cap-required): one run of this route uncapped, with the voice changer off (not one of the six runs), then a cap clearly below its Avg FPS and above 120 FPS. Write it down and use it for all six runs.
5. Keep everything else the same for all six runs: display mode, resolution, hero, the NVIDIA Reflex setting and Hardware-accelerated GPU scheduling.
6. Turn off "Listen to this device" on CABLE Output, as you would for a match.

## 2. Step 0: baseline (voice changer off, 3 runs)

1. Make sure the voice changer is not running: no `launch.bat` console and no "RVC - GUI" window.
2. Start Overwatch and go to the Practice Range.
3. Start the capture, play the route, and let the capture stop. Do this 3 times.
4. Fill in the three Baseline rows of the results table.

For stutter, note any hitch you see or feel and when. One hitch is not "recurring"; hitches that keep coming back during a run are. A "0.1% Low FPS" far below "Avg FPS" also points to stutter.

If the baseline 1% lows are already below 120 FPS, the runs with conversion on can't pass. Lower the graphics settings and redo the baseline.

## 3. Runs with conversion on (3 runs)

1. Start the voice changer with the preset you're testing, for example `launch.bat -Preset vctk-p231`.
2. Click **Start audio conversion** and check that **Output converted voice** is selected. With CUDA Graph on (the default), the console prints `CUDA Graph warm-up complete` before the audio starts.
3. Talk for a few seconds so start-up isn't part of the first run.
4. Start Overwatch with the same settings and cap as the baseline and make the same 3 captured runs. Talk during each run as you would in a match (callouts, counting aloud).
5. After each run, find the inference time for the fight. The window shows only the latest value, so scroll back in the console to the fight and note the highest `Inference time: ... seconds` value that keeps coming back.
6. Fill in the three Conversion rows: preset, Sample length (block_time), pitch detection algorithm (f0), Index Rate, FPS cap, frame-time numbers, stutter notes and inference time. Add the delay from [section 4](#4-measure-the-delay-measure-delayps1), measured with the same settings.

Note any non-default choice, for example `launch.bat -NoCudaGraph` or a ticked noise-reduction box.

## 4. Measure the delay (`measure-delay.ps1`)

The script records your raw mic and CABLE Output (what the game hears) at the same time with FFmpeg, finds where your "ta!" starts in each track, and prints the difference. It doesn't include the game's own voice-chat transmission. The window's "Algorithmic delays(ms):" is only an estimate from the settings; this is the measured value.

Before you start, conversion must be running with "Output converted voice" selected (Overwatch can stay closed), and the room must be quiet.

1. Open Command Prompt or PowerShell in the repo folder and list the capture devices FFmpeg sees:

   ```
   powershell -ExecutionPolicy Bypass -File scripts\measure-delay.ps1 -ListDevices
   ```

   It prints `DirectShow audio capture devices:` and one name per line, including `Microphone (Chat-Audeze Maxwell)` and `CABLE Output (VB-Audio Virtual Cable)`. Use these names here, not the ones from `launch.bat -ListDevices` (the engine's view).
2. By default the mic is the one device whose name contains both "Audeze Maxwell" and "Chat", and the cable is the one containing "CABLE Output" (not case-sensitive). For other names, pass your own parts, comma-separated inside one pair of quotes. This works in Command Prompt and PowerShell (the example repeats the defaults):

   ```
   powershell -ExecutionPolicy Bypass -File scripts\measure-delay.ps1 -Mic "Audeze Maxwell,Chat" -Cable "CABLE Output"
   ```

   Exactly one device must contain every part, or the script stops with `No DirectShow audio device matches ...` or `... devices match ...` and shows the list.
3. Run it (add `-Mic` / `-Cable` if you needed them):

   ```
   powershell -ExecutionPolicy Bypass -File scripts\measure-delay.ps1
   ```

   It prints the devices it picked (`Mic   : ...`, `Cable : ...`), then `Opening both devices. Stay quiet until GO, then say one short, sharp 'ta!' and stay quiet again.` Once both are open it counts down `3...`, `2...`, `1...`.
4. When `>>> GO: say "ta!" now <<<` appears, say one short, sharp "ta!", then stay quiet until the result appears (the recording is 12 s by default).
5. Read the result. Each track gets a line such as `Mic   : sound starts <n> s after GO (peak <n> dBFS, threshold <n> dB)`, followed by `End-to-end delay (cable - mic): <n> ms` and one verdict:
   - `Within the <= ~300 ms target.`
   - `Above the ~300 ms target. See docs\tuning.md (lower block_time, then extra_time).`
   - `This value is implausible: ...` (see [When the result looks wrong](#when-the-result-looks-wrong)).

   The exit code is 0 when a plausible delay was measured (even above the target), otherwise 1.
6. Measure 3 times with the same settings. The target asks for a stable delay, so the three values should be close. Write them in the results.

Each capture is saved as `captures\delay-<yyyyMMdd-HHmmss>.mkv` (mic = first audio track, CABLE Output = second), with a `.txt` report and a `.json` holding the GO time. Keep the `.json` next to the `.mkv`: `-Analyze` uses it to ignore sounds before GO.

| Parameter | Default | What it does |
|---|---|---|
| `-Mic` | `Audeze Maxwell`, `Chat` | Parts that must all appear in the mic's DirectShow name; one comma-separated string also works |
| `-Cable` | `CABLE Output` | Parts for the cable's recording side |
| `-Seconds` | 12 | Recording length |
| `-PromptAt` | 3 | Seconds of silence recorded after both devices are open, before GO |
| `-NoiseDb` | automatic: 20 dB below each track's peak, clamped to -60..-20 | Level (dBFS) below which audio counts as silence. A value (e.g. -25 or -40) forces one threshold for both tracks |
| `-BufferMs` | 15 | DirectShow audio buffer in ms |
| `-ListDevices` | | Print the DirectShow audio capture devices and exit |
| `-Analyze <file.mkv>` | | Analyze an existing capture instead of recording |

If opening the devices is slow, the script warns `Opening the devices took <n> s, so the first one may stop recording early.` and suggests a `-Seconds` value. Use it for the next run.

### Re-analyze a capture with another `-NoiseDb`

```
powershell -ExecutionPolicy Bypass -File scripts\measure-delay.ps1 -Analyze captures\delay-20260924-201500.mkv -NoiseDb -35
```

Use your own file name. `-Analyze` prints the result but doesn't write a new `.txt`. Raise the value (closer to 0 than the printed threshold, e.g. -25) if room noise fills the silence around the "ta!"; lower it (e.g. -40) if the "ta!" isn't detected.

### When the result looks wrong

Each of these means no valid delay was measured (exit code 1):

- `Mic   : silent (peak <n> dBFS). Is the mic muted, or is -Mic the wrong device?`, or `Cable : silent (peak <n> dBFS). Is the voice changer running, with 'Output converted voice' selected and CABLE Input as its output device?`: the track never got louder than -60 dBFS. Check what the message asks, then record again.
- `Mic   : no clear 'silence, then sound, then silence' after GO (peak <n> dBFS, threshold <n> dB). Stay quiet until GO and record again, or try -NoiseDb.` (or the same with `Cable :`): each track needs silence (at least 0.3 s), then sound, then silence again; sounds that start more than 0.5 s before GO are ignored. Record again, or re-analyze with another `-NoiseDb`. If the cable track keeps failing because room noise is converted between sounds, raise "Response threshold" only a little (it is -60, gate off, by default; try about -55) and record again ([tuning.md](tuning.md#response-threshold-noise-gate)).
- `This value is implausible: one track probably caught a different sound. Record again, or try -NoiseDb.`: the delay came out below 0 ms or above 1500 ms, usually because a click, breath or key press near GO counted as the start in one track. Stay silent until GO and record again, or re-analyze.

Also watch for `GO time : unknown (no .json next to the capture); the first sound in each track counts` (only with `-Analyze`: sounds before GO are no longer ignored), and for values that jump between runs (same causes as above; record again).

### Why the script uses wall-clock timestamps

FFmpeg opens the two devices one after the other, seconds apart, and normally shifts each input to start at zero on its own, so the two tracks would not line up. The script therefore:

- stamps both inputs with the same wall clock (`-use_wallclock_as_timestamps 1`), keeps those stamps in the `.mkv` (`-copyts`), and reads them back with `-copyts -start_at_zero`, which subtracts the same start time from both tracks;
- stamps GO on the same clock (saved in the `.json`) and shows it only once both devices are open, because what the first device records while the second is opening gets bunched-up timestamps;
- asks for a 15 ms DirectShow buffer (FFmpeg's default of about 500 ms makes the timestamps far too coarse) and opens each device by the plain-ASCII "Alternative name" FFmpeg lists for it;
- finds each onset with FFmpeg's `silencedetect`: the end of a silence that is followed by silence again. The delay is onset(cable) minus onset(mic).

## 5. One-minute CABLE Output recording

This is exactly what the game hears.

1. Start the voice changer, click **Start audio conversion**, and keep "Output converted voice" selected.
2. In a terminal in the repo folder, record 60 seconds (if there's no `captures` folder yet, create it with `mkdir captures`). Use the cable name that `measure-delay.ps1 -ListDevices` showed:

   ```
   ffmpeg -hide_banner -f dshow -i audio="CABLE Output (VB-Audio Virtual Cable)" -t 60 captures\cable-60s.wav
   ```

   This works in Command Prompt and PowerShell. FFmpeg asks before it overwrites a file; press `q` to stop early.
3. During the minute, talk normally: some quiet words, a loud callout, pauses of several seconds, and some breathing near the mic.
4. Play the file in any audio player and check:

| Problem | What it sounds like | What to do |
|---|---|---|
| Clipping | Harsh distortion on loud words | Lower the mic's "Input volume" on its properties page (the **>** arrow, as in [windows-audio.md](windows-audio.md#3-turn-off-enhancements-and-voice-clarity-set-communications-to-do-nothing)), then record again. |
| Dropouts | Gaps, clicks, crackle | Raise "Sample length" (block_time) with the [tuning loop](tuning.md#the-tuning-loop). |
| Echo | Your voice twice, or game and system sounds in the recording | CABLE Input is the default playback device, or "Listen to this device" plays into it. Fix the [default devices](windows-audio.md#right-after-installing-fix-the-default-devices) or [Listen to this device](windows-audio.md#6-hear-yourself-while-tuning-listen-to-this-device). |
| Gate chatter | Words cut in and out, or odd sounds between words | Words cut: check "Response threshold" is -60 (gate off), then "Inference time (ms)", then the Maxwell FILTER A.I. on low or off. Odd sounds: gate to about -55 ([tuning.md](tuning.md#response-threshold-noise-gate)). |

To put a number on clipping, run `ffmpeg -hide_banner -i captures\cable-60s.wav -af volumedetect -f null -`. `max_volume: 0.0 dB` means the audio reached full scale, which usually means clipping; the `histogram_0db` line counts the samples that did.

With VAC Lite instead of VB-CABLE, close any other app using the cable before you record ([windows-audio.md](windows-audio.md#fallback-vac-lite-if-vb-cable-crackles)).

## 6. Offline test

This proves that nothing needs the internet, an account or a subscription once everything is installed. Overwatch needs the internet, so this test runs without the game.

1. Make sure `install-engine.ps1` and `get-models.ps1` have finished and their checks passed.
2. Turn off Wi-Fi (or turn on Airplane mode), unplug any network cable, and restart the PC.
3. Run `launch.bat` and click **Start audio conversion**. With "Listen to this device" on ([windows-audio.md](windows-audio.md#6-hear-yourself-while-tuning-listen-to-this-device)), speak and check that you hear the converted voice. Turn it off again.
4. Press the hotkey twice. The radio button flips and the cue sounds play.
5. It passes if the window opens, conversion works, and the console shows no network or download errors. Reconnect the network.

## 7. Other verification checks

The plan's Verification list also asks for these. Record them in the second results table.

1. **Install checks:** `install-engine.ps1` printed `SHA256 OK: ...` when it installed the engine, and `get-models.ps1` ends with `Done: ... everything in models\ matches config\models.json.` (it re-checks every file on each run). Then double-click `engine\go-realtime_gui.bat`: the stock "RVC - GUI" window opens. Close it.
2. **Launch with a preset:** run `launch.bat -Preset vctk-p231`, check that the window shows the preset (its `.pth` file and "Pitch settings" +10), click **Start audio conversion**, and check through "Listen to this device" that you hear the converted voice. Turn it off again.
3. **Hotkey:** on the desktop, then with Overwatch focused in fullscreen and in borderless windowed mode, as in [overwatch.md](overwatch.md#check-the-hotkey-while-the-game-has-focus). Note which `"method"` worked.
4. **Presets:** close the RVC window, run `launch.bat -Preset vctk-p238`, and listen as in check 2. Then do the same with `vctk-p249`. Each voice should sound different.

## If acceptance still fails

The [plan](PLAN.md#fallbacks-only-if-step-5-acceptance-fails) has two fallbacks. This repo doesn't set up either one (`get-models.ps1 -IncludeBeatrice` only downloads the Beatrice zips):

- **B: VCClient v1.5.3.18a** (open source), benchmarked with the same voice and these same tests, and adopted only if it passes. The hotkey would toggle its passThrough setting through its local API at 127.0.0.1:18888, so block inbound port 18888 in the firewall.
- **C: no GPU.** The official Beatrice v2 VST (rc.3) in a free VST host, with the same voices' Beatrice zips. CPU only, about 50 ms, less realistic. Whether these January 2025 models load in rc.3 is unverified.

## Results

Tool: ______ (FrameView or PresentMon). Graphics settings: ______. Display mode: ______.

For the baseline rows, leave the voice changer columns as `-`. A conversion row passes when all four targets are met. Add rows when you re-test after a tuning change. The conversion rows start with the starting values (`config\audio.json` and the vctk-p231 preset); change them if you test something else.

| Run | Date | Preset | block_time | f0 | Index rate | FPS cap | Avg FPS | 1% low | Stutter notes | Inference ms | Delay ms | Pass/fail |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Baseline 1 | | off | - | - | - | | | | | - | - | - |
| Baseline 2 | | off | - | - | - | | | | | - | - | - |
| Baseline 3 | | off | - | - | - | | | | | - | - | - |
| Conversion 1 | | vctk-p231 | 0.25 | rmvpe | 0.5 | | | | | | | |
| Conversion 2 | | vctk-p231 | 0.25 | rmvpe | 0.5 | | | | | | | |
| Conversion 3 | | vctk-p231 | 0.25 | rmvpe | 0.5 | | | | | | | |

| Other check | Date | Result | Notes |
|---|---|---|---|
| Install checks: SHA256 OK in `install-engine.ps1` and `get-models.ps1`; stock `engine\go-realtime_gui.bat` opens | | | |
| `launch.bat -Preset vctk-p231`: preset loaded, converted voice heard via "Listen to this device" | | | |
| One-minute CABLE Output recording: clipping, dropouts, echo, gate chatter | | | |
| Hotkey: desktop / Overwatch fullscreen / borderless (radio flips, cue plays, no restart) | | | Method used: |
| Presets vctk-p238 and vctk-p249 sound different | | | |
| Offline test | | | |
| Delay, 3 measurements (ms) | | | |
